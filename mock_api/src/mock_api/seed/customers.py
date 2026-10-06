"""Customer identities. No Olist identifier or location reaches the API."""

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from datetime import datetime

from faker import Faker

from mock_api.seed.rand import rng
from mock_api.seed.rows import CustomerRow

# (town, Eircode routing keys, weight). Faker's en_IE towns are placeholders, so towns and
# postcodes come from this list instead.
TOWNS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("Dublin", ("D01", "D02", "D04", "D06", "D08", "D12", "D15", "D18", "D24"), 30),
    ("Cork", ("T12", "T23"), 10),
    ("Galway", ("H91",), 6),
    ("Limerick", ("V94",), 5),
    ("Waterford", ("X91",), 3),
    ("Drogheda", ("A92",), 2),
    ("Dundalk", ("A91",), 2),
    ("Swords", ("K67",), 2),
    ("Bray", ("A98",), 2),
    ("Navan", ("C15",), 2),
    ("Kilkenny", ("R95",), 2),
    ("Ennis", ("V95",), 2),
    ("Carlow", ("R93",), 1),
    ("Tralee", ("V92",), 1),
    ("Naas", ("W91",), 2),
    ("Athlone", ("N37",), 1),
    ("Sligo", ("F91",), 1),
    ("Letterkenny", ("F92",), 1),
    ("Mullingar", ("N91",), 1),
    ("Wexford", ("Y35",), 1),
    ("Castlebar", ("F23",), 1),
)
EIRCODE_CHARS = "ACDEFHKNPRTVWXY0123456789"
EMAIL_DOMAINS = ("example.com", "example.net", "example.org")
MOBILE_PREFIXES = ("83", "85", "86", "87", "89")


def _email_part(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", ascii_name.lower()) or "customer"


def build_customers(
    first_order_at: Mapping[str, datetime], seed: int
) -> tuple[dict[str, str], list[CustomerRow]]:
    """Return (Olist customer_unique_id -> Lumora customer id, rows).

    Customers are numbered by first order; Faker is called the same number of times per
    customer in that order, so the identities are stable for a given Faker version.
    """
    fake = Faker("en_IE")
    fake.seed_instance(seed)
    towns, routing_keys, weights = zip(*TOWNS, strict=True)

    ids: dict[str, str] = {}
    rows: list[CustomerRow] = []
    email_bases: Counter[str] = Counter()
    ordered = sorted(first_order_at, key=lambda u: (first_order_at[u], u))
    for number, unique_id in enumerate(ordered, start=1):
        customer_id = f"CUS-{number:06d}"
        first, last, street = fake.first_name(), fake.last_name(), fake.street_address()
        r = rng(seed, "customer", unique_id)

        base = f"{_email_part(first)}.{_email_part(last)}"
        email_bases[base] += 1
        suffix = "" if email_bases[base] == 1 else str(email_bases[base])
        town_index = r.choices(range(len(towns)), weights=weights)[0]
        routing = r.choice(routing_keys[town_index])
        unique = "".join(r.choice(EIRCODE_CHARS) for _ in range(4))

        ids[unique_id] = customer_id
        rows.append(
            CustomerRow(
                id=customer_id,
                name=f"{first} {last}",
                email=f"{base}{suffix}@{r.choice(EMAIL_DOMAINS)}",
                phone=(
                    f"+353 {r.choice(MOBILE_PREFIXES)} {r.randint(100, 999)} "
                    f"{r.randint(1000, 9999)}"
                ),
                address_line=street,
                city=towns[town_index],
                postcode=f"{routing} {unique}",
                country="IE",
                created_at=first_order_at[unique_id],
            )
        )
    return ids, rows

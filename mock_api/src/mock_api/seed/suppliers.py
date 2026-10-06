"""Mapping Olist sellers onto ~120 Lumora suppliers.

Each seller has a primary category (where it sells the most). Supplier slots are shared
out across categories with the D'Hondt method on item volume, and sellers are dealt
round-robin into their category's slots, so a supplier sells one kind of product.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping

from mock_api.seed.olist import OlistData
from mock_api.seed.rand import rng
from mock_api.seed.rows import SupplierRow

NAME_HEADS = (
    "Ash",
    "Bell",
    "Brook",
    "Cedar",
    "Clear",
    "Dale",
    "Elm",
    "Fair",
    "Fern",
    "Glen",
    "Hart",
    "Iron",
    "Kings",
    "Lark",
    "Mill",
    "Nord",
    "North",
    "Oak",
    "Pine",
    "River",
    "Stone",
    "Thorn",
    "West",
    "Wild",
)
NAME_TAILS = (
    "haven",
    "grove",
    "mont",
    "water",
    "wood",
    "field",
    "bridge",
    "ford",
    "stead",
    "brook",
    "gate",
    "holm",
)
CATEGORY_SUFFIXES: dict[str, tuple[str, ...]] = {
    "bedding_bath": ("Textiles", "Linens", "Home Textiles"),
    "decor": ("Interiors", "Design", "Home Decor"),
    "housewares": ("Housewares", "Kitchenware", "Homeware"),
    "home_office": ("Office Furniture", "Workspace"),
    "living_room": ("Furniture", "Furnishings"),
    "home_comfort": ("Living", "Soft Furnishings"),
    "dining_garden": ("Furniture", "Outdoor Living"),
    "lighting": ("Lighting", "Lamps"),
    "seasonal": ("Seasonal", "Festive"),
    "bedroom": ("Furniture", "Bedroom Furniture"),
    "kitchen_appliances": ("Appliances", "Electricals"),
    "mattresses": ("Sleep", "Beds"),
}
COUNTRIES = (
    ("Ireland", 18),
    ("United Kingdom", 16),
    ("Germany", 12),
    ("Portugal", 10),
    ("Poland", 10),
    ("Netherlands", 6),
    ("Italy", 8),
    ("Spain", 6),
    ("Turkey", 8),
    ("China", 4),
    ("India", 2),
)


def _allocate_slots(
    volume: Mapping[str, int], capacity: Mapping[str, int], total: int
) -> dict[str, int]:
    """D'Hondt allocation of `total` slots, at least one per category, capped by sellers."""
    slots = {c: 1 for c in volume}
    remaining = total - len(slots)
    while remaining > 0:
        open_categories = [c for c in volume if slots[c] < capacity[c]]
        if not open_categories:
            break
        best = max(open_categories, key=lambda c: (volume[c] / (slots[c] + 1), c))
        slots[best] += 1
        remaining -= 1
    return slots


def assign_suppliers(
    data: OlistData, categories: Mapping[str, str], count: int, seed: int
) -> tuple[dict[str, str], list[SupplierRow]]:
    """Return (Olist product_id -> supplier id, supplier rows)."""
    seller_categories: defaultdict[str, Counter[str]] = defaultdict(Counter)
    product_sellers: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for order_id in sorted(data.items):
        for item in data.items[order_id]:
            product = data.products.get(item.product_id)
            if product is None or product.category not in categories:
                continue
            seller_categories[item.seller_id][categories[product.category]] += 1
            product_sellers[item.product_id][item.seller_id] += 1

    sellers_by_category: defaultdict[str, list[str]] = defaultdict(list)
    volume: Counter[str] = Counter()
    for seller_id, counts in seller_categories.items():
        primary = min(counts, key=lambda c: (-counts[c], c))
        sellers_by_category[primary].append(seller_id)
        volume[primary] += sum(counts.values())

    capacity = {c: len(s) for c, s in sellers_by_category.items()}
    slots = _allocate_slots(volume, capacity, count)

    name_rng = rng(seed, "supplier-names")
    heads = [f"{h}{t}" for h in NAME_HEADS for t in NAME_TAILS]
    name_rng.shuffle(heads)

    suppliers: list[SupplierRow] = []
    seller_supplier: dict[str, str] = {}
    for category in sorted(slots, key=lambda c: (-volume[c], c)):
        ids: list[str] = []
        for _ in range(slots[category]):
            number = len(suppliers) + 1
            supplier_id = f"SUP-{number:03d}"
            r = rng(seed, "supplier", supplier_id)
            head = heads[(number - 1) % len(heads)]
            countries, weights = zip(*COUNTRIES, strict=True)
            suppliers.append(
                SupplierRow(
                    id=supplier_id,
                    name=f"{head} {r.choice(CATEGORY_SUFFIXES[category])}",
                    country=r.choices(countries, weights=weights)[0],
                    contact_email=f"orders@{head.lower()}.example",
                )
            )
            ids.append(supplier_id)
        ranked = sorted(
            sellers_by_category[category],
            key=lambda s: (-sum(seller_categories[s].values()), s),
        )
        for i, seller_id in enumerate(ranked):
            seller_supplier[seller_id] = ids[i % len(ids)]

    supplier_of_product = {
        product_id: seller_supplier[min(sellers, key=lambda s: (-sellers[s], s))]
        for product_id, sellers in product_sellers.items()
    }
    return supplier_of_product, suppliers

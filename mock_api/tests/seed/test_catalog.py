import random
import re

from mock_api.seed.catalog import CATEGORY_CODES, SUBTYPES, build_products, choose_subtype
from mock_api.seed.config import CATEGORY_MAP
from mock_api.seed.dataset import SeedDataset
from mock_api.seed.olist import OlistData

HYGIENE_TYPES = {
    "Pillowcase Pair",
    "Hand Towel",
    "Bath Towel",
    "Fitted Sheet",
    "Pillow",
    "Mattress Protector",
    "Sheet Set",
    "Duvet Cover Set",
    "Bathrobe",
    "Duvet",
    "Weighted Blanket",
    "Mattress Topper",
    "Mattress",
}


def test_every_lumora_category_has_subtypes_and_a_code() -> None:
    assert set(CATEGORY_MAP.values()) == SUBTYPES.keys() == CATEGORY_CODES.keys()
    for subtypes in SUBTYPES.values():
        for s in subtypes:
            assert s.min_g < s.max_g and s.freq > 0 and s.materials


def test_hygiene_comes_from_the_subtype() -> None:
    flagged = {s.label for subtypes in SUBTYPES.values() for s in subtypes if s.hygiene}
    assert flagged == HYGIENE_TYPES


def test_subtype_fits_weight_or_is_nearest() -> None:
    r = random.Random(0)
    for _ in range(50):
        chosen = choose_subtype("bedding_bath", 1200, r)
        assert chosen.min_g <= 1200 < chosen.max_g
    assert choose_subtype("living_room", 50, r).label == "Footstool"
    assert choose_subtype("mattresses", 25000, r).label in {"Mattress", "Upholstered Ottoman"}


def test_products_are_deterministic(olist_data: OlistData) -> None:
    supplier_of = {pid: "SUP-001" for pid in olist_data.products}
    first = build_products(olist_data, CATEGORY_MAP, supplier_of, 1, 0.2)
    second = build_products(olist_data, CATEGORY_MAP, supplier_of, 1, 0.2)
    assert first == second


def test_product_rows(dataset: SeedDataset) -> None:
    skus = [p.sku for p in dataset.products]
    assert len(skus) == len(set(skus))
    assert all(re.fullmatch(r"LUM-[A-Z]{3}-\d{5}", s) for s in skus)
    assert all(p.is_hygiene == (p.product_type in HYGIENE_TYPES) for p in dataset.products)
    assert any(p.is_outlet for p in dataset.products)
    assert all(p.list_price > 0 for p in dataset.products)
    assert {p.supplier_id for p in dataset.products} <= {s.id for s in dataset.suppliers}

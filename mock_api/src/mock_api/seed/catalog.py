"""Product catalog: names, SKUs, hygiene and outlet flags.

Olist has no product names. Each Lumora category has a list of subtypes; a product gets a
subtype that fits its Olist weight, and the subtype decides the name and the hygiene flag.
"""

import random
import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from mock_api.seed.olist import OlistData
from mock_api.seed.rand import rng, unit_hash
from mock_api.seed.rows import ProductRow

CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Subtype:
    label: str
    min_g: int
    max_g: int
    freq: int
    materials: tuple[str, ...]
    variants: tuple[str, ...] = ()
    hygiene: bool = False
    colours: bool = True


BED_SIZES = ("Single", "Double", "King", "Super King")
PILLOW_SIZES = ("Standard", "King")
FIRMNESS = ("Soft", "Medium", "Firm")
TABLE_SIZES = ("4-Seater", "6-Seater", "8-Seater")

SUBTYPES: dict[str, tuple[Subtype, ...]] = {
    "bedding_bath": (
        Subtype(
            "Pillowcase Pair",
            0,
            700,
            6,
            ("Cotton Percale", "Sateen", "Linen", "Bamboo"),
            PILLOW_SIZES,
            hygiene=True,
        ),
        Subtype("Hand Towel", 0, 600, 5, ("Cotton Terry", "Waffle Cotton"), hygiene=True),
        Subtype("Napkin Set", 0, 800, 3, ("Linen", "Cotton"), ("Set of 4", "Set of 6")),
        Subtype("Shower Curtain", 150, 900, 3, ("Waffle", "Recycled Polyester")),
        Subtype(
            "Bath Towel",
            300,
            1500,
            8,
            ("Cotton Terry", "Egyptian Cotton", "Waffle Cotton"),
            hygiene=True,
        ),
        Subtype("Bath Mat", 300, 1500, 4, ("Cotton", "Bamboo", "Memory Foam")),
        Subtype(
            "Tablecloth",
            300,
            2000,
            4,
            ("Linen", "Cotton", "Wipe-Clean"),
            ("140 x 180 cm", "150 x 250 cm", "Round 180 cm"),
        ),
        Subtype(
            "Fitted Sheet",
            400,
            1500,
            7,
            ("Cotton Percale", "Jersey", "Sateen"),
            BED_SIZES,
            hygiene=True,
        ),
        Subtype(
            "Pillow",
            400,
            2500,
            7,
            ("Microfibre", "Duck Feather", "Memory Foam"),
            PILLOW_SIZES,
            hygiene=True,
            colours=False,
        ),
        Subtype(
            "Curtain Panel Pair",
            600,
            4000,
            5,
            ("Blackout", "Linen Look", "Velvet"),
            ("137 cm drop", "183 cm drop", "229 cm drop"),
        ),
        Subtype(
            "Mattress Protector",
            700,
            3000,
            4,
            ("Waterproof", "Quilted Cotton"),
            BED_SIZES,
            hygiene=True,
            colours=False,
        ),
        Subtype(
            "Sheet Set",
            800,
            3000,
            7,
            ("Cotton Percale", "Sateen", "Linen", "Flannel"),
            BED_SIZES,
            hygiene=True,
        ),
        Subtype(
            "Duvet Cover Set",
            800,
            3000,
            8,
            ("Cotton Percale", "Sateen", "Linen", "Seersucker"),
            BED_SIZES,
            hygiene=True,
        ),
        Subtype(
            "Bathrobe",
            800,
            2000,
            3,
            ("Waffle Cotton", "Cotton Terry"),
            ("S/M", "L/XL"),
            hygiene=True,
        ),
        Subtype(
            "Duvet",
            1500,
            6000,
            5,
            ("Microfibre", "Duck Feather", "Wool"),
            ("4.5 Tog", "10.5 Tog", "13.5 Tog"),
            hygiene=True,
            colours=False,
        ),
        Subtype("Quilted Bedspread", 1500, 5000, 3, ("Cotton", "Velvet"), BED_SIZES),
    ),
    "decor": (
        Subtype("Photo Frame", 0, 800, 5, ("Oak", "Brass", "Black Metal"), ("10 x 15 cm", "A4")),
        Subtype("Candle Holder", 0, 1500, 4, ("Glass", "Brass", "Ceramic")),
        Subtype("Wall Art Print", 150, 3000, 4, ("Framed", "Canvas"), ("A3", "50 x 70 cm")),
        Subtype("Decorative Tray", 200, 1500, 3, ("Rattan", "Marble", "Mango Wood")),
        Subtype("Vase", 200, 4000, 5, ("Ceramic", "Glass", "Stoneware")),
        Subtype("Artificial Plant", 200, 5000, 3, ("Potted", "Hanging"), colours=False),
        Subtype("Wall Clock", 300, 2500, 3, ("Oak", "Metal", "Glass")),
        Subtype("Wall Mirror", 1000, 15000, 4, ("Round", "Arched", "Rectangular")),
        Subtype("Wall Shelf", 1000, 10000, 4, ("Oak", "Pine", "Metal")),
        Subtype("Side Table", 3000, 20000, 4, ("Oak", "Marble", "Metal")),
        Subtype("Storage Bench", 5000, 30000, 2, ("Rattan", "Upholstered", "Oak")),
        Subtype("Console Table", 5000, 30000, 2, ("Oak", "Walnut", "Metal")),
        Subtype("Bookcase", 8000, 40000, 3, ("Oak", "White", "Walnut"), ("3-Shelf", "5-Shelf")),
        Subtype("TV Unit", 10000, 60000, 2, ("Oak", "Walnut", "White Gloss")),
    ),
    "housewares": (
        Subtype("Water Bottle", 0, 700, 3, ("Stainless Steel", "Glass")),
        Subtype("Kitchen Utensil Set", 0, 1500, 4, ("Silicone", "Beech Wood", "Stainless Steel")),
        Subtype("Spice Rack", 200, 2000, 2, ("Bamboo", "Metal")),
        Subtype("Mug Set", 300, 2500, 4, ("Stoneware", "Porcelain"), ("Set of 4",)),
        Subtype(
            "Glass Tumbler Set",
            300,
            3000,
            3,
            ("Recycled Glass", "Ribbed Glass"),
            ("Set of 4", "Set of 6"),
            colours=False,
        ),
        Subtype("Chopping Board", 300, 3000, 3, ("Acacia", "Bamboo", "Marble"), colours=False),
        Subtype("Storage Jar Set", 300, 3000, 4, ("Glass", "Ceramic"), ("Set of 3",)),
        Subtype(
            "Food Storage Set",
            300,
            3000,
            3,
            ("Glass", "BPA-Free"),
            ("10-Piece", "16-Piece"),
            colours=False,
        ),
        Subtype(
            "Knife Set",
            500,
            3000,
            3,
            ("Stainless Steel", "Damascus Steel"),
            ("3-Piece", "5-Piece"),
            colours=False,
        ),
        Subtype(
            "Frying Pan",
            600,
            2500,
            4,
            ("Non-Stick", "Cast Iron", "Stainless Steel"),
            ("24 cm", "28 cm"),
            colours=False,
        ),
        Subtype("Saucepan", 600, 3000, 3, ("Stainless Steel", "Enamelled"), ("16 cm", "20 cm")),
        Subtype("Dinner Set", 1500, 8000, 3, ("Stoneware", "Porcelain"), ("12-Piece", "16-Piece")),
        Subtype("Casserole Dish", 1500, 6000, 3, ("Cast Iron", "Enamelled"), ("24 cm", "28 cm")),
        Subtype("Laundry Basket", 500, 4000, 3, ("Rattan", "Seagrass", "Cotton Rope")),
        Subtype("Pedal Bin", 1500, 8000, 3, ("Stainless Steel", "Matt"), ("20 L", "30 L")),
        Subtype("Clothes Airer", 1500, 8000, 2, ("Aluminium", "Steel"), colours=False),
        Subtype(
            "Cookware Set",
            3000,
            15000,
            2,
            ("Non-Stick", "Stainless Steel"),
            ("3-Piece", "5-Piece"),
            colours=False,
        ),
        Subtype("Ironing Board", 3000, 10000, 2, ("Steel",), ("Standard", "Compact")),
    ),
    "home_office": (
        Subtype("Desk Organiser", 0, 1500, 4, ("Bamboo", "Metal Mesh", "Leather")),
        Subtype("Monitor Stand", 800, 5000, 3, ("Oak", "Bamboo", "Metal")),
        Subtype("Footrest", 800, 4000, 2, ("Ergonomic",), colours=False),
        Subtype("Office Chair", 5000, 25000, 6, ("Mesh", "Upholstered", "Leather")),
        Subtype("Filing Cabinet", 8000, 40000, 2, ("Steel", "Oak"), ("2-Drawer", "3-Drawer")),
        Subtype("Writing Desk", 8000, 50000, 4, ("Oak", "Walnut", "White"), ("100 cm", "120 cm")),
        Subtype("Bookshelf", 8000, 30000, 2, ("Oak", "White"), ("4-Shelf", "5-Shelf")),
    ),
    "living_room": (
        Subtype("Footstool", 1000, 10000, 3, ("Velvet", "Boucle", "Leather")),
        Subtype("Nest of Tables", 4000, 20000, 3, ("Oak", "Walnut", "Marble")),
        Subtype("Coffee Table", 5000, 35000, 5, ("Oak", "Walnut", "Marble", "Glass")),
        Subtype("Armchair", 8000, 35000, 4, ("Velvet", "Boucle", "Linen")),
        Subtype("TV Stand", 8000, 40000, 3, ("Oak", "Walnut", "White Gloss")),
        Subtype("Sideboard", 15000, 60000, 3, ("Oak", "Walnut", "Rattan")),
        Subtype("Two-Seater Sofa", 20000, 80000, 2, ("Velvet", "Linen", "Leather")),
        Subtype("Three-Seater Sofa", 30000, 200000, 2, ("Velvet", "Linen", "Leather")),
    ),
    "home_comfort": (
        Subtype("Cushion Cover", 0, 600, 5, ("Linen", "Velvet", "Boucle"), ("45 x 45 cm",)),
        Subtype("Draught Excluder", 300, 1500, 2, ("Wool", "Tweed")),
        Subtype("Cushion", 300, 1800, 5, ("Velvet", "Linen", "Knitted"), ("45 x 45 cm",)),
        Subtype("Throw", 500, 2500, 5, ("Chunky Knit", "Wool", "Cotton Waffle")),
        Subtype(
            "Rug", 1000, 15000, 4, ("Jute", "Wool", "Washable"), ("120 x 170 cm", "160 x 230 cm")
        ),
        Subtype(
            "Weighted Blanket", 3000, 12000, 2, ("Cotton", "Bamboo"), ("5 kg", "7 kg"), hygiene=True
        ),
    ),
    "dining_garden": (
        Subtype("Plant Stand", 300, 5000, 3, ("Metal", "Bamboo", "Terracotta")),
        Subtype("Folding Chair", 2000, 8000, 3, ("Acacia", "Metal")),
        Subtype("Bar Stool", 3000, 12000, 4, ("Velvet", "Rattan", "Metal")),
        Subtype("Dining Chair Pair", 5000, 20000, 5, ("Oak", "Velvet", "Rattan")),
        Subtype("Bench", 5000, 25000, 3, ("Oak", "Acacia", "Metal")),
        Subtype("Garden Bistro Set", 8000, 30000, 3, ("Acacia", "Metal", "Rattan")),
        Subtype("Utility Cabinet", 8000, 40000, 2, ("White", "Oak")),
        Subtype("Dining Table", 15000, 80000, 4, ("Oak", "Walnut", "Marble"), TABLE_SIZES),
    ),
    "lighting": (
        Subtype(
            "LED Bulb Pack", 0, 400, 4, ("Warm White", "Smart"), ("E27", "GU10"), colours=False
        ),
        Subtype(
            "String Lights", 0, 1500, 3, ("Copper Wire", "Festoon"), ("5 m", "10 m"), colours=False
        ),
        Subtype("Wall Light", 300, 3000, 3, ("Brass", "Black Metal", "Opal Glass")),
        Subtype("Pendant Light", 300, 4000, 4, ("Rattan", "Brass", "Glass")),
        Subtype("Table Lamp", 500, 4000, 5, ("Ceramic", "Brass", "Oak")),
        Subtype("Ceiling Light", 500, 6000, 3, ("Flush", "Semi-Flush")),
        Subtype("Floor Lamp", 2000, 12000, 4, ("Arc", "Tripod", "Brass")),
    ),
    "seasonal": (
        Subtype("Christmas Stocking", 0, 600, 3, ("Knitted", "Velvet")),
        Subtype(
            "Fairy Lights",
            0,
            1000,
            4,
            ("Warm White", "Multicolour"),
            ("100 LED", "200 LED"),
            colours=False,
        ),
        Subtype("Bauble Set", 100, 1500, 4, ("Glass", "Shatterproof"), ("Set of 12", "Set of 24")),
        Subtype("Advent Calendar", 200, 2000, 2, ("Wooden", "Fabric"), colours=False),
        Subtype("Nativity Set", 200, 3000, 2, ("Resin", "Wooden"), colours=False),
        Subtype("Wreath", 300, 2500, 3, ("Eucalyptus", "Pine Cone", "Berry"), colours=False),
        Subtype(
            "Artificial Christmas Tree",
            2000,
            25000,
            3,
            ("Nordic Fir", "Snowy Spruce"),
            ("5 ft", "6 ft", "7 ft"),
            colours=False,
        ),
    ),
    "bedroom": (
        Subtype(
            "Bedside Table", 3000, 20000, 5, ("Oak", "Walnut", "White"), ("1-Drawer", "2-Drawer")
        ),
        Subtype("Headboard", 5000, 25000, 3, ("Velvet", "Linen", "Rattan"), BED_SIZES[1:]),
        Subtype("Dressing Table", 10000, 40000, 2, ("Oak", "White")),
        Subtype(
            "Chest of Drawers",
            15000,
            60000,
            4,
            ("Oak", "Walnut", "White"),
            ("3-Drawer", "5-Drawer"),
        ),
        Subtype("Bed Frame", 20000, 90000, 3, ("Oak", "Upholstered", "Metal"), BED_SIZES[1:]),
        Subtype("Wardrobe", 30000, 150000, 2, ("Oak", "White"), ("2-Door", "3-Door")),
    ),
    "kitchen_appliances": (
        Subtype("Milk Frother", 0, 1000, 2, ("Electric",), colours=False),
        Subtype("Hand Blender", 400, 2000, 3, ("Stainless Steel",), ("600 W", "1000 W")),
        Subtype("Kettle", 800, 2000, 5, ("Stainless Steel", "Matt", "Glass"), ("1.7 L",)),
        Subtype("Toaster", 1000, 3000, 4, ("Stainless Steel", "Matt"), ("2-Slice", "4-Slice")),
        Subtype("Sandwich Maker", 1000, 3000, 2, ("Non-Stick",)),
        Subtype("Coffee Maker", 1500, 6000, 4, ("Filter", "Pour-Over")),
        Subtype("Food Processor", 2000, 7000, 2, ("Compact", "Multi")),
        Subtype("Air Fryer", 3000, 8000, 4, ("Digital",), ("4 L", "6 L")),
        Subtype("Espresso Machine", 3000, 12000, 3, ("Bean-to-Cup", "Pump")),
        Subtype("Stand Mixer", 4000, 12000, 2, ("Tilt-Head",), ("4.8 L",)),
    ),
    "mattresses": (
        Subtype(
            "Mattress Topper",
            1500,
            10000,
            4,
            ("Memory Foam", "Microfibre"),
            BED_SIZES,
            hygiene=True,
            colours=False,
        ),
        Subtype("Upholstered Ottoman", 5000, 25000, 2, ("Velvet", "Linen")),
        Subtype(
            "Mattress",
            8000,
            60000,
            6,
            ("Pocket Sprung", "Memory Foam", "Hybrid"),
            tuple(f"{size}, {firm}" for size in BED_SIZES for firm in FIRMNESS),
            hygiene=True,
            colours=False,
        ),
    ),
}

CATEGORY_CODES: dict[str, str] = {
    "bedding_bath": "BED",
    "decor": "DEC",
    "housewares": "HSW",
    "home_office": "OFF",
    "living_room": "LIV",
    "home_comfort": "CMF",
    "dining_garden": "DIN",
    "lighting": "LGT",
    "seasonal": "SEA",
    "bedroom": "BRM",
    "kitchen_appliances": "KAP",
    "mattresses": "MAT",
}

COLLECTIONS = (
    "Alder",
    "Aster",
    "Birch",
    "Brae",
    "Calla",
    "Cove",
    "Drift",
    "Dune",
    "Elm",
    "Ember",
    "Fern",
    "Fjord",
    "Glen",
    "Hale",
    "Isla",
    "Juniper",
    "Kerry",
    "Larch",
    "Linden",
    "Lough",
    "Maple",
    "Marlow",
    "Moss",
    "Ness",
    "Nora",
    "Orla",
    "Oslo",
    "Pebble",
    "Quill",
    "Rowan",
    "Shore",
    "Sorrel",
    "Tamsin",
    "Tide",
    "Vale",
    "Willow",
    "Wren",
    "Yarrow",
)
COLOURS = (
    "Sage",
    "Oat",
    "Charcoal",
    "Ivory",
    "Navy",
    "Terracotta",
    "Dusk Blue",
    "Sand",
    "Stone",
    "Blush",
    "Ochre",
    "White",
    "Graphite",
    "Forest Green",
    "Clay",
)


def choose_subtype(category: str, weight_g: int | None, r: random.Random) -> Subtype:
    """A subtype whose weight range fits; the nearest range if none does."""
    subtypes = SUBTYPES[category]
    if weight_g is None:
        candidates = list(subtypes)
    else:
        candidates = [s for s in subtypes if s.min_g <= weight_g < s.max_g]
        if not candidates:

            def distance(s: Subtype) -> int:
                return s.min_g - weight_g if weight_g < s.min_g else weight_g - s.max_g + 1

            nearest = min(distance(s) for s in subtypes)
            candidates = [s for s in subtypes if distance(s) == nearest]
    return r.choices(candidates, weights=[s.freq for s in candidates])[0]


def product_name(subtype: Subtype, r: random.Random) -> str:
    base = f"{r.choice(COLLECTIONS)} {r.choice(subtype.materials)} {subtype.label}"
    details: list[str] = []
    if subtype.variants:
        details.append(r.choice(subtype.variants))
    if subtype.colours:
        details.append(r.choice(COLOURS))
    return f"{base} – {', '.join(details)}" if details else base


def build_products(
    data: OlistData,
    categories: Mapping[str, str],
    supplier_of_product: Mapping[str, str],
    seed: int,
    outlet_share: float,
) -> dict[str, ProductRow]:
    """Every Olist product in a mapped category, keyed by Olist product_id."""
    prices: defaultdict[str, list[Decimal]] = defaultdict(list)
    for items in data.items.values():
        for item in items:
            prices[item.product_id].append(item.price)

    by_category: defaultdict[str, list[str]] = defaultdict(list)
    for product_id, product in data.products.items():
        if product.category in categories and product_id in prices:
            by_category[categories[product.category]].append(product_id)

    rows: dict[str, ProductRow] = {}
    for category in sorted(by_category):
        # SKU numbers follow a hash order, so they carry no trace of Olist ordering.
        ordered = sorted(by_category[category], key=lambda p: (unit_hash(seed, "sku", p), p))
        for number, product_id in enumerate(ordered, start=10001):
            olist = data.products[product_id]
            r = rng(seed, "product", product_id)
            subtype = choose_subtype(category, olist.weight_g, r)
            rows[product_id] = ProductRow(
                sku=f"LUM-{CATEGORY_CODES[category]}-{number:05d}",
                name=product_name(subtype, r),
                category=category,
                product_type=subtype.label,
                supplier_id=supplier_of_product[product_id],
                list_price=Decimal(statistics.median(prices[product_id])).quantize(CENT),
                weight_g=olist.weight_g,
                length_cm=olist.length_cm,
                height_cm=olist.height_cm,
                width_cm=olist.width_cm,
                is_hygiene=subtype.hygiene,
                is_outlet=unit_hash(seed, "outlet", product_id) < outlet_share,
            )
    return rows

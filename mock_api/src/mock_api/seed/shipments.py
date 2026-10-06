"""Fictional carriers and tracking numbers."""

import random
import string

from mock_api.seed.rand import unit_hash

FREIGHT_CARRIER = "Hollis Freight"
FREIGHT_THRESHOLD_G = 20_000
PARCEL_CARRIERS = (("Parcelo", 0.40), ("NordPost", 0.35), ("SwiftLane Express", 0.25))


def choose_carrier(order_key: str, total_weight_g: int, seed: int) -> str:
    """Heavy orders go by freight; the rest are split across parcel carriers by hash."""
    if total_weight_g > FREIGHT_THRESHOLD_G:
        return FREIGHT_CARRIER
    point = unit_hash(seed, "carrier", order_key)
    cumulative = 0.0
    for carrier, share in PARCEL_CARRIERS:
        cumulative += share
        if point < cumulative:
            return carrier
    return PARCEL_CARRIERS[-1][0]


def _digits(r: random.Random, n: int) -> str:
    return "".join(r.choice(string.digits) for _ in range(n))


def tracking_number(carrier: str, r: random.Random) -> str:
    match carrier:
        case "Parcelo":
            return f"PCL{_digits(r, 12)}"
        case "NordPost":
            return f"NP{_digits(r, 9)}IE"
        case "SwiftLane Express":
            letters = "".join(r.choice(string.ascii_uppercase) for _ in range(4))
            return f"SLX-{letters}-{_digits(r, 6)}"
        case _:
            return f"HF{_digits(r, 8)}"

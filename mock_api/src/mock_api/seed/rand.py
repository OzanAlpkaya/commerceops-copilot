"""Deterministic randomness.

Each decision draws from its own generator keyed by (seed, domain, key), so adding a step
or changing one domain never reshuffles another. random.Random seeded with a str hashes it
with SHA-512, which does not depend on PYTHONHASHSEED.
"""

import hashlib
import random


def rng(seed: int, domain: str, key: str = "") -> random.Random:
    return random.Random(f"{seed}:{domain}:{key}")


def unit_hash(seed: int, domain: str, key: str) -> float:
    """A stable number in [0, 1) for (seed, domain, key)."""
    digest = hashlib.sha256(f"{seed}:{domain}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64

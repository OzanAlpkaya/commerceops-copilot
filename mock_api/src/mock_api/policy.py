"""Lumora's return policy parameters, read from config/policy_params.yaml.

The file is the single source of truth for policy version dates, return windows and
return fees: the seed reads it so seeded outcomes follow the written policy, and the
document corpus is rendered from it.
"""

from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from mock_api.enums import ReturnReason

DEFAULT_PATH = Path("config/policy_params.yaml")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PolicyVersion(_Frozen):
    orders_from: date
    orders_until: date | None = None
    window_days: int
    window_start: Literal["order", "delivery"]
    return_shipping_fee: bool


class Versions(_Frozen):
    v1: PolicyVersion
    v2: PolicyVersion

    @model_validator(mode="after")
    def _contiguous(self) -> "Versions":
        if self.v1.orders_until is None or self.v2.orders_until is not None:
            raise ValueError("v1 needs orders_until and v2 must be open-ended")
        if self.v1.orders_until + timedelta(days=1) != self.v2.orders_from:
            raise ValueError("v2 must start the day after v1 ends")
        return self


class Claims(_Frozen):
    damaged_report_days: int
    wrong_item_report_days: int
    defective_days: int


class ReturnFee(_Frozen):
    parcel: Decimal
    collection: Decimal


class Collection(_Frozen):
    carrier: str
    threshold_kg: int


class DeliveryService(_Frozen):
    carriers: tuple[str, ...]
    typical_days: tuple[int, int]
    price_eur: tuple[Decimal, Decimal]


class Delivery(_Frozen):
    standard_parcel: DeliveryService
    large_item: DeliveryService


class PolicyParams(_Frozen):
    versions: Versions
    claims: Claims
    return_fees_eur: dict[ReturnReason, ReturnFee]
    collection: Collection
    refund_working_days: int
    delivery: Delivery

    def version_id(self, placed_on: date) -> Literal["v1", "v2"]:
        """The policy version that applies to an order placed on `placed_on`."""
        return "v2" if placed_on >= self.versions.v2.orders_from else "v1"

    def version(self, placed_on: date) -> PolicyVersion:
        return getattr(self.versions, self.version_id(placed_on))


@cache
def load_policy_params(path: Path = DEFAULT_PATH) -> PolicyParams:
    with path.open(encoding="utf-8") as f:
        return PolicyParams.model_validate(yaml.safe_load(f))

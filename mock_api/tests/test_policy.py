from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from mock_api.enums import ReturnReason
from mock_api.policy import DEFAULT_PATH, PolicyParams, load_policy_params
from mock_api.seed.config import SeedConfig
from mock_api.seed.shipments import FREIGHT_CARRIER, FREIGHT_THRESHOLD_G


def test_repo_file_loads() -> None:
    params = load_policy_params(DEFAULT_PATH)
    assert params.versions.v2.orders_from == date(2026, 3, 1)
    assert params.versions.v1.orders_until == date(2026, 2, 28)
    fee = params.return_fees_eur[ReturnReason.CHANGED_MIND]
    assert (fee.parcel, fee.collection) == (Decimal("4.95"), Decimal("29.00"))


def test_version_by_order_date() -> None:
    params = load_policy_params(DEFAULT_PATH)
    assert params.version_id(date(2026, 2, 28)) == "v1"
    assert params.version_id(date(2026, 3, 1)) == "v2"
    assert params.version(date(2025, 1, 1)).window_start == "delivery"


def test_collection_matches_the_seed_carrier_rule() -> None:
    params = load_policy_params(DEFAULT_PATH)
    assert params.collection.carrier == FREIGHT_CARRIER
    assert params.collection.threshold_kg * 1000 == FREIGHT_THRESHOLD_G
    assert params.delivery.large_item.carriers == (FREIGHT_CARRIER,)


def test_seed_reads_the_file() -> None:
    cfg = SeedConfig(_env_file=None)  # type: ignore[call-arg]
    assert cfg.policy_change == date(2026, 3, 1)
    assert cfg.return_window_days == 30


def test_versions_must_be_contiguous() -> None:
    raw = yaml.safe_load(DEFAULT_PATH.read_text())
    raw["versions"]["v2"]["orders_from"] = date(2026, 3, 2)
    with pytest.raises(ValidationError, match="day after v1"):
        PolicyParams.model_validate(raw)


def test_seed_rejects_different_window_lengths(tmp_path: Path) -> None:
    raw = yaml.safe_load(DEFAULT_PATH.read_text())
    raw["versions"]["v1"]["window_days"] = 14
    path = tmp_path / "params.yaml"
    path.write_text(yaml.safe_dump(raw))
    cfg = SeedConfig(_env_file=None, policy_params=path)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="same window length"):
        _ = cfg.return_window_days

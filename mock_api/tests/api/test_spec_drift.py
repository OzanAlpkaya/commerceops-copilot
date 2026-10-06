"""The static openapi.yaml handed to the client is partly outdated on purpose.

These tests pin exactly how it differs from what the API returns, so the drift stays
deliberate and matches the list in mock_api/README.md.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from mock_api.enums import LegacyOrderStatus, OrderStatus
from mock_api.main import OPENAPI_YAML
from mock_api.schemas import (
    CustomerOut,
    OrderItemOut,
    OrderSummaryOut,
    ProductOut,
    ReturnItemOut,
    ReturnOut,
    ShipmentOut,
)

README = Path(__file__).parents[2] / "README.md"

# spec schema -> (model, fields only in the spec, fields only in the API)
EXPECTED_DRIFT: dict[str, tuple[type[BaseModel], set[str], set[str]]] = {
    "Customer": (CustomerOut, {"first_name", "last_name"}, {"name"}),
    "Product": (ProductOut, set(), {"is_hygiene", "is_outlet"}),
    "OrderSummary": (
        OrderSummaryOut,
        {"total"},
        {"total_amount", "currency", "coupon_code", "discount_amount"},
    ),
    "OrderItem": (OrderItemOut, set(), set()),
    "Shipment": (ShipmentOut, {"tracking_url", "eta"}, {"estimated_delivery_at"}),
    "Return": (ReturnOut, set(), set()),
    "ReturnItem": (ReturnItemOut, set(), set()),
}


def spec() -> dict[str, Any]:
    return yaml.safe_load(OPENAPI_YAML.read_text())


def test_spec_is_openapi_3() -> None:
    document = spec()
    assert document["openapi"].startswith("3.")
    assert document["components"]["securitySchemes"]["ApiKey"]["name"] == "X-API-Key"


def test_field_drift_is_exactly_the_planned_one() -> None:
    schemas = spec()["components"]["schemas"]
    for name, (model, spec_only, api_only) in EXPECTED_DRIFT.items():
        documented = set(schemas[name]["properties"])
        actual = set(model.model_fields)
        assert (documented - actual, actual - documented) == (spec_only, api_only), name


def test_status_enum_lists_only_the_current_values() -> None:
    documented = set(spec()["components"]["schemas"]["OrderStatus"]["enum"])
    assert documented == {s.value for s in OrderStatus}
    assert not documented & {s.value for s in LegacyOrderStatus}


def test_rate_limits_and_scopes_are_undocumented() -> None:
    text = OPENAPI_YAML.read_text()
    assert '"429"' not in text and "Retry-After" not in text
    assert "scope" not in text.lower()


def test_readme_lists_the_drift() -> None:
    readme = README.read_text()
    section = readme[readme.index("### Spec drift") :]
    for _, spec_only, api_only in EXPECTED_DRIFT.values():
        for field in spec_only | api_only:
            assert f"`{field}`" in section, field

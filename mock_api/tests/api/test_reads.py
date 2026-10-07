from collections.abc import Callable
from typing import get_args

from fastapi.testclient import TestClient

from mock_api.enums import LegacyOrderStatus, OrderStatus
from mock_api.routers.orders import StatusFilter

Headers = Callable[..., dict[str, str]]


def test_order_with_items(client: TestClient, headers: Headers) -> None:
    order = client.get("/orders/LH-1000002", headers=headers()).json()

    assert order["status"] == "delivered"
    assert order["coupon_code"] == "SPRING15"
    assert order["total_amount"] == "110.00"  # money as a decimal string
    assert [(i["line_no"], i["sku"], i["quantity"]) for i in order["items"]] == [
        (1, "LUM-BED-10001", 1),
        (2, "LUM-DEC-10002", 3),
    ]
    assert order["items"][0]["product_name"] == "Aster Microfibre Pillow – King"


def test_shipment(client: TestClient, headers: Headers) -> None:
    shipment = client.get("/orders/LH-1000003/shipment", headers=headers()).json()
    assert (shipment["status"], shipment["delivered_at"]) == ("in_transit", None)
    assert shipment["estimated_delivery_at"].startswith("2026-10-08")


def test_product_flags(client: TestClient, headers: Headers) -> None:
    pillow = client.get("/products/LUM-BED-10001", headers=headers()).json()
    vase = client.get("/products/LUM-DEC-10002", headers=headers()).json()
    assert (pillow["is_hygiene"], pillow["is_outlet"]) == (True, False)
    assert (vase["is_hygiene"], vase["is_outlet"]) == (False, True)


def test_filters(client: TestClient, headers: Headers) -> None:
    by_email = client.get(
        "/customers", params={"email": "Aoife.Murphy@EXAMPLE.com"}, headers=headers()
    )
    assert [c["id"] for c in by_email.json()["data"]] == ["CUS-000001"]
    by_supplier = client.get("/products", params={"supplier_id": "SUP-001"}, headers=headers())
    assert len(by_supplier.json()["data"]) == 3
    assert client.get("/products", params={"supplier_id": "SUP-999"}, headers=headers()).json() == {
        "data": [],
        "next_cursor": None,
    }


def test_not_found_uses_the_error_envelope(client: TestClient, headers: Headers) -> None:
    cases = {
        "/customers/CUS-999999": "customer_not_found",
        "/orders/LH-0": "order_not_found",
        "/orders/LH-0/shipment": "order_not_found",
        "/products/LUM-XXX-00000": "product_not_found",
        "/returns/RMA-1": "return_not_found",
        "/no/such/path": "not_found",
    }
    for path, code in cases.items():
        response = client.get(path, headers=headers())
        assert response.status_code == 404
        assert response.json()["error"]["code"] == code


# Legacy enum -------------------------------------------------------------------------


def test_legacy_orders_return_the_stored_status(client: TestClient, headers: Headers) -> None:
    assert client.get("/orders/LH-1000001", headers=headers()).json()["status"] == "COMPLETED"


def test_status_filter_matches_literally(client: TestClient, headers: Headers) -> None:
    def ids(status: str) -> list[str]:
        params = {"customer_id": "CUS-000001", "status": status}
        return [
            o["id"] for o in client.get("/orders", params=params, headers=headers()).json()["data"]
        ]

    assert ids("delivered") == ["LH-1000002"]  # the legacy COMPLETED order is not included
    assert ids("COMPLETED") == ["LH-1000001"]


def test_unknown_status_is_422(client: TestClient, headers: Headers) -> None:
    response = client.get("/orders", params={"status": "done"}, headers=headers())
    assert response.status_code == 422


def test_status_filter_accepts_both_enums() -> None:
    assert set(get_args(StatusFilter)) == {s.value for s in (*OrderStatus, *LegacyOrderStatus)}

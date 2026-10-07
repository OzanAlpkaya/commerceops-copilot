from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from mock_api.config import parse_api_keys

Headers = Callable[..., dict[str, str]]
RETURN = {
    "order_id": "LH-1000002",
    "reason": "defective",
    "items": [{"order_item_id": 2, "quantity": 1, "condition": "opened"}],
}


def test_missing_key_is_401(client: TestClient) -> None:
    response = client.get("/orders/LH-1000001")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_wrong_key_is_401(client: TestClient, headers: Headers) -> None:
    assert client.get("/orders/LH-1000001", headers=headers("not-a-key")).status_code == 401


@pytest.mark.parametrize("who", ["copilot", "admin", "ops"])
def test_each_configured_key_can_read(client: TestClient, headers: Headers, who: str) -> None:
    assert client.get("/orders/LH-1000001", headers=headers(who)).status_code == 200


def test_read_only_key_cannot_create_returns(client: TestClient, headers: Headers) -> None:
    response = client.post(
        "/returns", json=RETURN, headers=headers("copilot", **{"Idempotency-Key": "k1"})
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_scope"


def test_public_endpoints_need_no_key(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    spec = client.get("/openapi.yaml")
    assert spec.status_code == 200 and spec.text.startswith("openapi:")


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_generated_docs_are_disabled(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_no_keys_configured_means_no_access(make_client, headers: Headers) -> None:
    client = make_client(keys="")
    assert client.get("/orders/LH-1000001", headers=headers()).status_code == 401


def test_key_config_parsing() -> None:
    clients = parse_api_keys("copilot:abc:read, admin:def:read+write")
    assert [(c.name, sorted(c.scopes)) for c in clients] == [
        ("copilot", ["read"]),
        ("admin", ["read", "write"]),
    ]
    for bad in ("copilot:abc", "copilot:abc:delete", "a:same:read,b:same:read"):
        with pytest.raises(ValueError):
            parse_api_keys(bad)

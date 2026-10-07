from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from mock_api.models import IdempotencyKey, Return

Headers = Callable[..., dict[str, str]]
BODY = {
    "order_id": "LH-1000002",
    "reason": "defective",
    "items": [{"order_item_id": 2, "quantity": 1, "condition": "opened"}],
    "customer_comment": "The pillow is lumpy.",
}


def post(client: TestClient, headers: Headers, key: str | None, body=BODY, who: str = "admin"):
    extra = {"Idempotency-Key": key} if key is not None else {}
    return client.post("/returns", json=body, headers=headers(who, **extra))


def count(engine: Engine, model) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def test_missing_key_is_400(client, headers, engine) -> None:
    for key in (None, "", "   "):
        response = post(client, headers, key)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "idempotency_key_required"
    assert count(engine, Return) == 1  # only the fixture's return


def test_creates_a_requested_return(client, headers) -> None:
    response = post(client, headers, "k-1")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "RMA-100002"  # continues the RMA- sequence
    assert response.headers["Location"] == "/returns/RMA-100002"
    assert (body["status"], body["source"], body["resolution"]) == ("requested", "api", None)
    assert body["items"] == [{"order_item_id": 2, "quantity": 1, "condition": "opened"}]
    assert client.get("/returns/RMA-100002", headers=headers()).json() == body


def test_same_key_same_body_replays(client, headers, engine) -> None:
    first = post(client, headers, "k-1")
    second = post(client, headers, "k-1")

    assert second.status_code == 201
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert "Idempotent-Replayed" not in first.headers
    assert count(engine, Return) == 2


def test_same_key_different_body_is_422(client, headers, engine) -> None:
    post(client, headers, "k-1")
    other = {**BODY, "customer_comment": "Changed my mind about the comment."}

    response = post(client, headers, "k-1", body=other)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "idempotency_key_reused"
    assert count(engine, Return) == 2


def test_keys_are_per_client(client, headers, engine) -> None:
    ours = post(client, headers, "shared", who="admin")
    body = {**BODY, "items": [{"order_item_id": 3, "quantity": 1, "condition": "unopened"}]}
    theirs = post(client, headers, "shared", body=body, who="ops")

    assert ours.status_code == theirs.status_code == 201
    assert ours.json()["id"] != theirs.json()["id"]
    with Session(engine) as session:
        clients = session.scalars(select(Return.api_client).where(Return.source == "api"))
        assert sorted(c or "" for c in clients) == ["admin", "ops"]


def test_failed_requests_are_not_stored(client, headers, engine) -> None:
    wrong = {**BODY, "items": [{"order_item_id": 4, "quantity": 1, "condition": "opened"}]}

    rejected = post(client, headers, "k-1", body=wrong)
    fixed = post(client, headers, "k-1")

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "item_not_in_order"
    assert fixed.status_code == 201
    assert count(engine, IdempotencyKey) == 1


def test_structural_checks(client, headers) -> None:
    cases = [
        ({**BODY, "order_id": "LH-9999999"}, 404, "order_not_found"),
        (
            {
                **BODY,
                "order_id": "LH-1000003",
                "items": [{"order_item_id": 4, "quantity": 1, "condition": "unopened"}],
            },
            422,
            "order_not_delivered",
        ),
        (
            # Line 3 has quantity 3 and one unit was already returned in RMA-100001.
            {**BODY, "items": [{"order_item_id": 3, "quantity": 3, "condition": "unopened"}]},
            422,
            "quantity_exceeds_returnable",
        ),
        ({**BODY, "reason": "too_expensive"}, 422, "validation_error"),
        ({**BODY, "items": []}, 422, "validation_error"),
        ({**BODY, "items": BODY["items"] * 2}, 422, "validation_error"),
        ({**BODY, "surprise": True}, 422, "validation_error"),
    ]
    for i, (body, status, code) in enumerate(cases):
        response = post(client, headers, f"k-{i}", body=body)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), body


def test_no_policy_window_is_enforced(client, headers) -> None:
    """Like the real order system: a legacy order delivered in 2025 still accepts a return."""
    body = {
        **BODY,
        "order_id": "LH-1000001",
        "items": [{"order_item_id": 1, "quantity": 2, "condition": "unopened"}],
    }
    assert post(client, headers, "old", body=body).status_code == 201


def test_rejected_returns_free_their_quantity(client, headers, engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE returns SET status = 'rejected' WHERE id = 'RMA-100001'"))
    body = {**BODY, "items": [{"order_item_id": 3, "quantity": 3, "condition": "unopened"}]}
    assert post(client, headers, "k-1", body=body).status_code == 201

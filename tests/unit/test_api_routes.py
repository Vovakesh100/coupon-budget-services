"""HTTP tests for the four routes. Use in-memory fakes, so no Redis or PostgreSQL is needed."""

import itertools
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from coupon_budget.api.app import create_app
from coupon_budget.config.rules import Rules
from coupon_budget.services.coupons import CouponService
from tests.fakes.memory_budget_store import MemoryBudgetStore
from tests.fakes.memory_repository import MemoryCampaignRepository

NOW = datetime(2026, 6, 1, tzinfo=UTC)
ENDS_ISO = (NOW + timedelta(days=30)).isoformat()
RULES = Rules(
    version=1,
    idempotency_key_ttl_seconds=86400,
    max_campaign_budget_micro=1_000_000,
    max_coupon_face_value_micro=200_000,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    ids = (f"id-{n}" for n in itertools.count(1))
    service = CouponService(
        records=MemoryCampaignRepository(),
        budget=MemoryBudgetStore(RULES.idempotency_key_ttl_seconds),
        rules=RULES,
        clock=lambda: NOW,
        new_id=lambda: next(ids),
    )
    with TestClient(create_app(service=service)) as test_client:
        yield test_client


def _campaign(client: TestClient, total: int = 500_000) -> str:
    resp = client.post("/campaigns", json={"total_micro": total, "ends_at": ENDS_ISO})
    assert resp.status_code == 201
    campaign_id: str = resp.json()["id"]
    return campaign_id


def _coupon(client: TestClient, campaign_id: str, face: int = 120_000) -> str:
    resp = client.post(f"/campaigns/{campaign_id}/coupons", json={"face_value_micro": face})
    assert resp.status_code == 201
    coupon_id: str = resp.json()["id"]
    return coupon_id


def test_create_campaign_returns_201_with_integer_budget(client: TestClient) -> None:
    resp = client.post("/campaigns", json={"total_micro": 500_000, "ends_at": ENDS_ISO})
    assert resp.status_code == 201
    body = resp.json()
    assert body["total_micro"] == 500_000
    assert isinstance(body["total_micro"], int)


@pytest.mark.parametrize("bad", [1.5, "500", True])
def test_create_campaign_rejects_non_integer_budget(client: TestClient, bad: object) -> None:
    resp = client.post("/campaigns", json={"total_micro": bad, "ends_at": ENDS_ISO})
    assert resp.status_code == 422


def test_create_campaign_rejects_unknown_fields(client: TestClient) -> None:
    resp = client.post(
        "/campaigns", json={"total_micro": 1, "ends_at": ENDS_ISO, "owner": "x"}
    )
    assert resp.status_code == 422


def test_create_campaign_over_limit_is_422(client: TestClient) -> None:
    resp = client.post(
        "/campaigns",
        json={"total_micro": RULES.max_campaign_budget_micro + 1, "ends_at": ENDS_ISO},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "limit_exceeded"


def test_issue_coupon_for_unknown_campaign_is_404(client: TestClient) -> None:
    resp = client.post("/campaigns/ghost/coupons", json={"face_value_micro": 1})
    assert resp.status_code == 404
    assert resp.json()["error"] == "campaign_not_found"


def test_redeem_requires_idempotency_key(client: TestClient) -> None:
    campaign_id = _campaign(client)
    coupon_id = _coupon(client, campaign_id)
    resp = client.post(f"/coupons/{coupon_id}/redeem")
    assert resp.status_code == 422


def test_redeem_then_budget_shows_spend(client: TestClient) -> None:
    campaign_id = _campaign(client)
    coupon_id = _coupon(client, campaign_id, face=120_000)
    resp = client.post(f"/coupons/{coupon_id}/redeem", headers={"Idempotency-Key": "k-1"})
    assert resp.status_code == 200
    assert resp.json()["redeemed"] is True

    budget = client.get(f"/campaigns/{campaign_id}/budget").json()
    assert budget == {
        "campaign_id": campaign_id,
        "allocated_micro": 500_000,
        "spent_micro": 120_000,
        "remaining_micro": 380_000,
    }


def test_same_idempotency_key_does_not_charge_twice(client: TestClient) -> None:
    campaign_id = _campaign(client)
    coupon_id = _coupon(client, campaign_id, face=120_000)
    headers = {"Idempotency-Key": "k-1"}
    assert client.post(f"/coupons/{coupon_id}/redeem", headers=headers).status_code == 200
    assert client.post(f"/coupons/{coupon_id}/redeem", headers=headers).status_code == 200
    budget = client.get(f"/campaigns/{campaign_id}/budget").json()
    assert budget["spent_micro"] == 120_000


def test_second_redemption_with_new_key_is_409(client: TestClient) -> None:
    campaign_id = _campaign(client)
    coupon_id = _coupon(client, campaign_id)
    client.post(f"/coupons/{coupon_id}/redeem", headers={"Idempotency-Key": "k-1"})
    resp = client.post(f"/coupons/{coupon_id}/redeem", headers={"Idempotency-Key": "k-2"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "coupon_already_redeemed"


def test_redeem_beyond_budget_is_409_and_leaves_budget_unchanged(client: TestClient) -> None:
    campaign_id = _campaign(client, total=100_000)
    first = _coupon(client, campaign_id, face=100_000)
    second = _coupon(client, campaign_id, face=1)
    client.post(f"/coupons/{first}/redeem", headers={"Idempotency-Key": "k-1"})
    resp = client.post(f"/coupons/{second}/redeem", headers={"Idempotency-Key": "k-2"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "budget_exceeded"
    budget = client.get(f"/campaigns/{campaign_id}/budget").json()
    assert budget["spent_micro"] == 100_000


def test_redeem_unknown_coupon_is_404(client: TestClient) -> None:
    resp = client.post("/coupons/ghost/redeem", headers={"Idempotency-Key": "k-1"})
    assert resp.status_code == 404
    assert resp.json()["error"] == "coupon_not_found"


def test_budget_for_unknown_campaign_is_404(client: TestClient) -> None:
    resp = client.get("/campaigns/ghost/budget")
    assert resp.status_code == 404
    assert resp.json()["error"] == "campaign_not_found"

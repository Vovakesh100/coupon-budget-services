"""Contract checks on the generated OpenAPI schema. No HTTP client needed.

The routes must match docs/TZ.md exactly. Changing them requires an owner decision.
"""

from datetime import UTC, datetime
from typing import Any

from coupon_budget.api.app import create_app
from coupon_budget.config.rules import Rules
from coupon_budget.services.coupons import CouponService
from tests.fakes.memory_budget_store import MemoryBudgetStore
from tests.fakes.memory_repository import MemoryCampaignRepository


def _app() -> Any:
    rules = Rules(
        version=1,
        idempotency_key_ttl_seconds=86400,
        max_campaign_budget_micro=1,
        max_coupon_face_value_micro=1,
    )
    service = CouponService(
        records=MemoryCampaignRepository(),
        budget=MemoryBudgetStore(rules.idempotency_key_ttl_seconds),
        rules=rules,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    return create_app(service=service)


def test_routes_match_the_tz_exactly() -> None:
    paths = _app().openapi()["paths"]
    assert set(paths) == {
        "/campaigns",
        "/campaigns/{campaign_id}/coupons",
        "/coupons/{coupon_id}/redeem",
        "/campaigns/{campaign_id}/budget",
    }
    assert set(paths["/campaigns"]) == {"post"}
    assert set(paths["/campaigns/{campaign_id}/coupons"]) == {"post"}
    assert set(paths["/coupons/{coupon_id}/redeem"]) == {"post"}
    assert set(paths["/campaigns/{campaign_id}/budget"]) == {"get"}


def test_redeem_requires_idempotency_key_header() -> None:
    op = _app().openapi()["paths"]["/coupons/{coupon_id}/redeem"]["post"]
    headers = [p for p in op["parameters"] if p["in"] == "header"]
    assert len(headers) == 1
    assert headers[0]["name"] == "Idempotency-Key"
    assert headers[0]["required"] is True


def test_money_fields_are_integers_in_the_schema() -> None:
    schemas = _app().openapi()["components"]["schemas"]
    assert schemas["CreateCampaignIn"]["properties"]["total_micro"]["type"] == "integer"
    assert schemas["CreateCouponIn"]["properties"]["face_value_micro"]["type"] == "integer"
    assert schemas["BudgetOut"]["properties"]["remaining_micro"]["type"] == "integer"

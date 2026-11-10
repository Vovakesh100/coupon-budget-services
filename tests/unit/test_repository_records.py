from datetime import UTC, datetime

import pytest

from coupon_budget.ports.repositories import CampaignRecord, CouponRecord

ENDS = datetime(2027, 1, 1, tzinfo=UTC)


def test_campaign_record_accepts_valid_values() -> None:
    record = CampaignRecord(id="cmp-1", total_micro=1_000_000, ends_at=ENDS)
    assert record.total_micro == 1_000_000


def test_campaign_record_rejects_naive_end_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CampaignRecord(id="cmp-1", total_micro=1, ends_at=datetime(2027, 1, 1))


@pytest.mark.parametrize("bad", [-1, 1.5, True])
def test_campaign_record_rejects_non_integer_or_negative_total(bad: object) -> None:
    with pytest.raises(ValueError, match="micro"):
        CampaignRecord(id="cmp-1", total_micro=bad, ends_at=ENDS)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_id", ["", "x" * 65])
def test_record_rejects_empty_or_too_long_id(bad_id: str) -> None:
    with pytest.raises(ValueError, match="id must be"):
        CampaignRecord(id=bad_id, total_micro=1, ends_at=ENDS)


def test_coupon_record_accepts_valid_values() -> None:
    record = CouponRecord(id="cpn-1", campaign_id="cmp-1", face_value_micro=100)
    assert record.face_value_micro == 100


def test_coupon_record_rejects_negative_face_value() -> None:
    with pytest.raises(ValueError, match="micro"):
        CouponRecord(id="cpn-1", campaign_id="cmp-1", face_value_micro=-5)

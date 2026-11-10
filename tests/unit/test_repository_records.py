from datetime import UTC, datetime, timedelta

import pytest

from coupon_budget.ports.repositories import CampaignRecord, CouponRecord

ENDS = datetime(2027, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 6, 1, tzinfo=UTC)


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


def test_coupon_record_unredeemed_has_no_redeemed_at() -> None:
    record = CouponRecord(id="cpn-1", campaign_id="cmp-1", face_value_micro=100)
    assert record.redeemed is False
    assert record.redeemed_at is None


def test_coupon_record_redeemed_requires_timestamp() -> None:
    with pytest.raises(ValueError, match="redeemed_at"):
        CouponRecord(id="cpn-1", campaign_id="cmp-1", face_value_micro=100, redeemed=True)


def test_coupon_record_timestamp_requires_redeemed_flag() -> None:
    with pytest.raises(ValueError, match="redeemed_at"):
        CouponRecord(
            id="cpn-1", campaign_id="cmp-1", face_value_micro=100, redeemed_at=NOW
        )


def test_coupon_record_redeemed_at_must_be_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CouponRecord(
            id="cpn-1",
            campaign_id="cmp-1",
            face_value_micro=100,
            redeemed=True,
            redeemed_at=datetime(2026, 6, 1),
        )


def test_coupon_record_accepts_redeemed_with_aware_timestamp() -> None:
    record = CouponRecord(
        id="cpn-1",
        campaign_id="cmp-1",
        face_value_micro=100,
        redeemed=True,
        redeemed_at=NOW + timedelta(hours=1),
    )
    assert record.redeemed

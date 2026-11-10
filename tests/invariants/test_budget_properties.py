from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from coupon_budget.domain.budget import Budget, BudgetExceededError, Campaign
from coupon_budget.domain.coupon import Coupon, redeem
from coupon_budget.domain.money import Money

NOW = datetime(2026, 6, 1, tzinfo=UTC)
ENDS = datetime(2027, 1, 1, tzinfo=UTC)


@given(
    total=st.integers(min_value=0, max_value=10**6),
    faces=st.lists(st.integers(min_value=1, max_value=10**4), max_size=50),
)
def test_spent_never_exceeds_budget(total: int, faces: list[int]) -> None:
    campaign = Campaign(id="c", budget=Budget(Money(total)), ends_at=ENDS)
    charged = 0
    for i, face in enumerate(faces):
        coupon = Coupon(id=f"k{i}", campaign_id="c", face_value=Money(face))
        before = campaign
        try:
            campaign, _ = redeem(campaign, coupon, NOW)
        except BudgetExceededError:
            assert campaign is before  # a refused redemption changes nothing
            assert charged + face > total
            continue
        charged += face
        assert campaign.budget.spent.micro == charged
        assert campaign.budget.spent.micro <= total

# Open questions

1. ~~Which atomicity strategy for the MVP?~~ **Answered:** Redis Lua script (option A), see `docs/adr/0001-atomicity-strategy.md`.
2. How long is an `Idempotency-Key` remembered? Proposed default: 24 hours.
3. What happens to a coupon whose campaign expires between issue and redemption?
4. Can a coupon be partially redeemed, or only in full?
5. Should the budget state endpoint show reserved amounts, or only spent and remaining?

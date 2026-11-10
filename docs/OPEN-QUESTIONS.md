# Open questions

1. ~~Which atomicity strategy for the MVP?~~ **Answered:** Redis Lua script (option A), see `docs/adr/0001-atomicity-strategy.md`.
2. **Idempotency-Key lifetime:** 24 hours. Answered: default accepted by the owner.
3. **Campaign expires between issue and redemption:** redemption is refused after the campaign end time with a clear error; the coupon is not charged. Answered: default accepted by the owner (the default was not written out before, now it is).
4. **Partial redemption:** only full redemption in the MVP. Answered: default accepted by the owner (the default was not written out before, now it is).
5. **Budget state endpoint:** shows spent and remaining only, no reserved amounts in the MVP. Answered: default accepted by the owner (the default was not written out before, now it is).

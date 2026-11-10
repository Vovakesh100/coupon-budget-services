# ADR 0001: Atomicity strategy for budget operations

Status: Proposed. The decision is pending the owner's choice.

## Context
Redeeming a coupon must check the remaining budget and decrement it in one step. Two concurrent redemptions must not both succeed when only one unit of budget is left.

## Options

### A. Redis Lua script
- Plus: one round trip; atomic by design; fits the high-load story.
- Minus: the logic lives in Lua, which is harder to test and read; keys must be designed for Redis Cluster in advance.

### B. PostgreSQL transaction with `SELECT ... FOR UPDATE` on the campaign row
- Plus: simple to reason about; the database is the single source of truth; easy to test.
- Minus: lower throughput under contention on one campaign row; Redis is not used.

### C. Both: PostgreSQL as source of truth, Redis as a fast counter, reconciled periodically
- Plus: closest to a real system; demonstrates reconciliation.
- Minus: the most code and the most failure modes for a demo.

## Consequences
Whichever option is chosen, the same invariant tests must pass: `spent <= budget` and no double charge for the same idempotency key.

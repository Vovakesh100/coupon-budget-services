# ADR 0002: Storage split between PostgreSQL and Redis

Status: Accepted (owner approved the proposal on 2026-11-10)

## Context

ADR 0001 puts the budget check and charge into one Redis Lua script, so Redis holds the
authoritative spend. The service also needs durable records of which campaigns and coupons
were issued. TZ and TASKS T7 call for PostgreSQL repositories.

## Decision

- PostgreSQL stores campaign and coupon records: `campaigns(id, total_micro, ends_at)` and
  `coupons(id, campaign_id, face_value_micro, redeemed, redeemed_at)`.
- Spend and the atomic redemption check stay in Redis. PostgreSQL never stores `spent`
  or the remaining balance.
- Access goes through `CampaignRepository` in `ports/repositories.py`. The adapter uses
  SQLAlchemy 2 async over asyncpg, and the schema is created by Alembic migrations.
- Amounts are `BIGINT` micro units with `CHECK (>= 0)`. Ids are `VARCHAR(64)`.
- A coupon's redeemed state is checked by the Lua script in Redis, not by PostgreSQL.

## Consequences

- Known gap: `redeemed` and `redeemed_at` in PostgreSQL are not updated by the redemption
  path yet. Until a sync step exists, PostgreSQL can show a coupon as unredeemed after Redis
  redeemed it. T8 must either sync these fields or stop reading them.
- Two stores must agree on campaigns and coupons. A coupon written to PostgreSQL but not
  to Redis (or the reverse) can make redemption fail with "not found". Ordering of writes
  and recovery after a partial failure are not designed yet.
- The 64-character id limit is a schema choice. Changing it needs a new migration.
- Dependencies SQLAlchemy, asyncpg and Alembic were not in the project rules list. They are
  part of the approved proposal, but the project rules list should be updated to match.

## Alternatives considered

- Keep everything in Redis. Simpler, but records would not survive a Redis eviction or
  restart without persistence settings, and reporting queries would be awkward.
- Plain asyncpg without SQLAlchemy. Fewer layers, but more hand-written SQL and no
  declarative migration tooling. Rejected for this portfolio project.

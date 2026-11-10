# ADR 0002: Storage split between PostgreSQL and Redis

Status: Accepted (owner approved the proposal on 2026-11-10). Amended 2026-11-10: `redeemed` and `redeemed_at` removed from PostgreSQL (migration 0002), see Decision.

## Context

ADR 0001 puts the budget check and charge into one Redis Lua script, so Redis holds the
authoritative spend. The service also needs durable records of which campaigns and coupons
were issued. TZ and TASKS T7 call for PostgreSQL repositories.

## Decision

- PostgreSQL stores campaign and coupon records: `campaigns(id, total_micro, ends_at)` and
  `coupons(id, campaign_id, face_value_micro)`.
- Redemption status is not stored in PostgreSQL. Redis is the only source of truth for it.
  The first draft had `redeemed` and `redeemed_at` columns with no sync path; migration 0002
  removed them to avoid two sources of truth.
- Spend and the atomic redemption check stay in Redis. PostgreSQL never stores `spent`
  or the remaining balance.
- Access goes through `CampaignRepository` in `ports/repositories.py`. The adapter uses
  SQLAlchemy 2 async over asyncpg, and the schema is created by Alembic migrations.
- Amounts are `BIGINT` micro units with `CHECK (>= 0)`. Ids are `VARCHAR(64)`.
- A coupon's redeemed state is checked by the Lua script in Redis, not by PostgreSQL.

## Consequences

- Reports that need "was this coupon redeemed?" must read Redis. PostgreSQL cannot answer it.
- Two stores still have to agree on campaigns and coupons. A coupon written to PostgreSQL
  but not to Redis (or the reverse) makes redemption fail with "not found". The write order
  and recovery after a partial failure are not designed yet; T8 must define them.
- The 64-character id limit is a schema choice. Changing it needs a new migration.
- Dependencies SQLAlchemy, asyncpg and Alembic were not in the `CLAUDE.md` list. They are
  part of the approved proposal, but the `CLAUDE.md` list should be updated to match.

## Alternatives considered

- Keep everything in Redis. Simpler, but records would not survive a Redis eviction or
  restart without persistence settings, and reporting queries would be awkward.
- Plain asyncpg without SQLAlchemy. Fewer layers, but more hand-written SQL and no
  declarative migration tooling. Rejected for this portfolio project.

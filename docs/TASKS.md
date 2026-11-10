# Tasks

Each task: one branch `task/<id>-<slug>`, one PR into `main`, linked to a TZ item. Status: `todo`, `in-progress`, `done`.

## T1: Project skeleton
- Status: done
- Depends on: none
- Do: `pyproject.toml` (Python 3.12, uv, ruff, mypy strict on `src/coupon_budget/domain`, pytest, Hypothesis), package layout `src/coupon_budget/{domain,ports,adapters,services,api,config}`, `tests/{unit,invariants,integration}`, `.gitignore`, `.env.example` with variable names only, one smoke test.
- Acceptance:
  1. `uv sync` completes.
  2. `uv run ruff check .`, `uv run mypy .`, `uv run pytest` pass.
  3. `src/coupon_budget/domain/` imports nothing from FastAPI, Redis or SQLAlchemy (checked by a test).

## T2: Money type (domain)
- Status: done
- Depends on: T1
- Do: `domain/money.py`: integer micro amounts, no `float`, round down on any conversion.
- Acceptance: unit tests and a Hypothesis test for arithmetic; `float` is rejected by the type or constructor.
- TZ: criterion 4.

## T3: Campaign and coupon rules (domain, pure)
- Status: done
- Depends on: T2
- Do: `domain/budget.py`, `domain/coupon.py`: `spent <= budget`, expiry check, full redemption only.
- Acceptance: Hypothesis property `spent <= budget` over random operation sequences; expired campaign refuses redemption; partial redemption is impossible.
- TZ: criteria 1, MVP 1–2.

## T4: Settings file (versioned)
- Status: done
- Depends on: T1
- Do: `config/` loads limits and expiry rules from a versioned settings file; nothing hard-coded in code.
- Acceptance: test shows a new settings version is applied (TZ criterion 5).

## T5: Budget store port and fake
- Status: done
- Depends on: T3
- Do: `ports/budget_store.py` interface and an in-memory fake used by service tests.
- Acceptance: service tests use only the fake; no Redis in unit tests.

## T6: Redis Lua adapter
- Status: todo
- Depends on: T5
- Do: `adapters/redis_budget.py` runs the budget check and decrement as one Lua script; idempotency key stored with 24-hour TTL; keys share a hash tag per campaign.
- Acceptance: integration test with a real Redis (testcontainers): duplicate `Idempotency-Key` does not charge twice; N parallel redemptions do not exceed the budget (TZ criteria 2, 3).

## T7: PostgreSQL repositories
- Status: todo
- Depends on: T5
- Do: `adapters/pg_repo.py` for campaigns and coupons (SQLAlchemy async or plain asyncpg, decided in an ADR if it differs from CLAUDE.md).
- Acceptance: integration test; schema and migration strategy need an owner decision before this task starts (ask first).

## T8: HTTP API
- Status: todo
- Depends on: T6, T7
- Do: four routes from TZ: `POST /campaigns`, `POST /campaigns/{id}/coupons`, `POST /coupons/{id}/redeem` (with `Idempotency-Key`), `GET /campaigns/{id}/budget`.
- Acceptance: API tests; OpenAPI generated; the routes match TZ exactly.

## T9: Docker Compose and README
- Status: todo
- Depends on: T8
- Do: `docker-compose.yml` with the service, Redis 7 and PostgreSQL 16; `.env.example` names only; README quick start works.
- Acceptance: `docker compose up` starts all three; health check responds.

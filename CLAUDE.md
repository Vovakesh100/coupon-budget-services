# CLAUDE.md: coupon-budget-service

Instructions for AI agents working in this repository. Read this file and `docs/TZ.md` before changing anything.

## Purpose
An HTTP service that issues coupons against campaign budgets. Redemption is atomic and idempotent, and the budget is never overspent. Portfolio demo project: synthetic data only, not client work.

## Stack
- Python 3.12, FastAPI, Pydantic v2, uvicorn (server)
- Redis 7: budget spend and redemption state, changed only by the Lua script
- PostgreSQL 16: campaign and coupon records. SQLAlchemy 2 (async) over asyncpg. Schema by Alembic migrations
- Client for tests: httpx (dev only)
- Tooling: uv, ruff, mypy (strict), pytest, Hypothesis, Docker Compose
- Integration tests use `DATABASE_URL` and `REDIS_URL` pointing at local services. testcontainers is not used yet (see docs/TASKS.md T6, T9)
- Async tests run with `asyncio.run`. pytest-asyncio is not installed

## Structure
- `src/coupon_budget/domain/`: `money.py`, `budget.py`, `coupon.py`. Pure logic, no I/O
- `src/coupon_budget/ports/`: interfaces. `budget_store.py` (Redis-side state), `repositories.py` (PostgreSQL records)
- `src/coupon_budget/adapters/`: `redis_budget.py` (Lua), `pg_repo.py` and `pg_models.py` (PostgreSQL)
- `src/coupon_budget/services/coupons.py`: orchestration. Writes the PostgreSQL record first, then Redis
- `src/coupon_budget/api/`: `app.py` (factory), `routes.py` (the four TZ routes), `schemas.py`, `errors.py`
- `src/coupon_budget/config/`: `rules.py` (versioned settings), `database.py` (URLs from the environment)
- `settings/rules.v1.toml`: business limits. A new version is a new file
- `migrations/`, `alembic.ini`: schema history. Current head is `0002`
- `tests/unit/`, `tests/invariants/` (Hypothesis), `tests/integration/`, `tests/fakes/`
- `docs/TZ.md` (requirements), `docs/TASKS.md` (task list), `docs/OPEN-QUESTIONS.md`, `docs/adr/`

## Rules
- Money is always an integer number of micro units. Never use `float` for amounts. Round down when a conversion is needed. Request and response bodies use strict integers.
- Every budget-changing operation is atomic (Lua script in Redis) and idempotent by `Idempotency-Key`.
- `domain/` must not import FastAPI, redis, SQLAlchemy, asyncpg or any other I/O library. `tests/unit/test_domain_isolation.py` enforces this.
- Business limits come from the versioned settings file, not from constants in code.
- Redemption state lives only in Redis. Do not add `redeemed` columns to PostgreSQL (ADR 0002).
- Never commit secrets, `.env` files or real data. `.env.example` lists variable names only.
- Tests use synthetic data only. Integration tests migrate `DATABASE_URL`, so point it at a disposable database.
- Code identifiers, file names, and commit messages are in English.

## Workflow
- One task per branch, named `task/T<n>-<slug>`. One PR per task, linked to a TZ item in `docs/TASKS.md`.
- Never push to `main`. Open a PR and merge it after checks pass.
- Before finishing a task, all of these must pass:
  - `uv run ruff check .`
  - `uv run mypy .`
  - `uv run pytest` (with `DATABASE_URL` and `REDIS_URL` set for the integration tests)
  - `uv run alembic check` when models or migrations change
- Use `gh api` REST calls to open and merge PRs. GraphQL-based `gh pr create` is blocked in the agent sandbox.
- Mark the task `done` in `docs/TASKS.md` in the same PR.

## Local services for integration tests
```
export DATABASE_URL="postgresql+asyncpg://<user>:<password>@localhost:5432/<test_db>"
export REDIS_URL="redis://localhost:6379/0"
```
Without these variables the integration tests skip. They do not fail.

## Stop and ask the owner before
- choosing the atomicity strategy, storage split, or schema changes beyond the approved migrations;
- changing any API route, route path, request body, or the `Idempotency-Key` behaviour;
- adding a dependency not listed in this file. Update this list in the same PR when one is approved;
- changing the rounding rule or the write order between PostgreSQL and Redis (services/coupons.py);
- pushing to `main`, or changing repository visibility.

## Approved dependencies
Runtime: fastapi, pydantic, uvicorn, redis, sqlalchemy[asyncio], asyncpg, alembic.
Dev: pytest, hypothesis, ruff, mypy, httpx.

## Open items
- Health check is liveness only. A readiness route needs an owner decision.
- Redis Cluster is out of scope. Lua keys use a per-campaign hash tag so that it could be added later.
- testcontainers is not in use. Revisit when CI with Docker exists.

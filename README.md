# coupon-budget-service

An HTTP service that issues coupons against campaign budgets. A coupon can be redeemed only while budget remains, and concurrent requests never overspend. Amounts are integers in micro units.

> Status: work in progress. Portfolio demo project.

## Quick start

```bash
cp .env.example .env
docker compose up
```

## API

- `POST /campaigns`: create a campaign with a budget
- `POST /campaigns/{id}/coupons`: issue a coupon
- `POST /coupons/{id}/redeem`: redeem a coupon (send `Idempotency-Key`)
- `GET /campaigns/{id}/budget`: budget state

## Development

```bash
uv sync
uv run ruff check .
uv run mypy .
uv run pytest
```

## Architecture

Domain logic has no I/O. Redis and PostgreSQL sit behind interfaces in `ports/`. The budget invariant (`spent <= budget`) is checked by property tests and concurrency tests. See `docs/TZ.md` and `docs/adr/`.

## Known limitations

- Not implemented yet. The list will be filled in before the first release.

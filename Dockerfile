FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:${PATH}"

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, so code changes do not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY settings ./settings

RUN useradd --create-home --uid 10001 app \
    && chown -R app /app
USER app

EXPOSE 8000

# Liveness only: the process answers HTTP. It does not check PostgreSQL or Redis.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=2)"

# Apply migrations, then serve. exec makes uvicorn PID 1 so it receives stop signals.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn coupon_budget.api.app:create_app --factory --host 0.0.0.0 --port 8000"]

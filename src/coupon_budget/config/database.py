"""Database connection settings. Read from the environment only, never stored in code."""

from __future__ import annotations

from collections.abc import Mapping

from coupon_budget.config.rules import SettingsError

DATABASE_URL_ENV_VAR = "DATABASE_URL"


def database_url_from_env(environ: Mapping[str, str]) -> str:
    url = environ.get(DATABASE_URL_ENV_VAR, "").strip()
    if not url:
        raise SettingsError(f"{DATABASE_URL_ENV_VAR} is not set")
    return url


REDIS_URL_ENV_VAR = "REDIS_URL"


def redis_url_from_env(environ: Mapping[str, str]) -> str:
    url = environ.get(REDIS_URL_ENV_VAR, "").strip()
    if not url:
        raise SettingsError(f"{REDIS_URL_ENV_VAR} is not set")
    return url

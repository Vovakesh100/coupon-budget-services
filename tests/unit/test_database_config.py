import pytest

from coupon_budget.config.database import database_url_from_env
from coupon_budget.config.rules import SettingsError


def test_reads_database_url_from_environment() -> None:
    url = database_url_from_env({"DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db"})
    assert url == "postgresql+asyncpg://u:p@localhost/db"


@pytest.mark.parametrize("environ", [{}, {"DATABASE_URL": ""}, {"DATABASE_URL": "   "}])
def test_missing_or_blank_database_url_is_an_error(environ: dict[str, str]) -> None:
    with pytest.raises(SettingsError, match="DATABASE_URL"):
        database_url_from_env(environ)

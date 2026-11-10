from pathlib import Path

import pytest

from coupon_budget.config.rules import SettingsError, load_rules, load_rules_from_env

REPO_RULES = Path(__file__).resolve().parents[2] / "settings" / "rules.v1.toml"

VALID = """
version = 1
[limits]
idempotency_key_ttl_seconds = 60
max_campaign_budget_micro = 1000
max_coupon_face_value_micro = 100
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "rules.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_repository_rules_file_loads() -> None:
    rules = load_rules(REPO_RULES)
    assert rules.version == 1
    assert rules.idempotency_key_ttl_seconds == 86400


def test_loads_values_from_file(tmp_path: Path) -> None:
    rules = load_rules(_write(tmp_path, VALID))
    assert rules.idempotency_key_ttl_seconds == 60
    assert rules.max_campaign_budget_micro == 1000


def test_new_settings_version_is_applied(tmp_path: Path) -> None:
    old = load_rules(_write(tmp_path, VALID))
    changed = VALID.replace("idempotency_key_ttl_seconds = 60", "idempotency_key_ttl_seconds = 120")
    new = load_rules(_write(tmp_path, changed))
    assert old.idempotency_key_ttl_seconds == 60
    assert new.idempotency_key_ttl_seconds == 120


def test_missing_key_is_an_error_not_a_default(tmp_path: Path) -> None:
    text = VALID.replace("max_coupon_face_value_micro = 100\n", "")
    with pytest.raises(SettingsError, match="max_coupon_face_value_micro"):
        load_rules(_write(tmp_path, text))


def test_float_value_rejected(tmp_path: Path) -> None:
    text = VALID.replace("max_campaign_budget_micro = 1000", "max_campaign_budget_micro = 10.5")
    with pytest.raises(SettingsError):
        load_rules(_write(tmp_path, text))


def test_unknown_version_rejected(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="version"):
        load_rules(_write(tmp_path, VALID.replace("version = 1", "version = 99")))


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="not found"):
        load_rules(tmp_path / "absent.toml")


def test_env_variable_points_to_file(tmp_path: Path) -> None:
    path = _write(tmp_path, VALID)
    assert load_rules_from_env({"SETTINGS_FILE": str(path)}).version == 1


def test_env_variable_must_be_set() -> None:
    with pytest.raises(SettingsError, match="SETTINGS_FILE"):
        load_rules_from_env({})

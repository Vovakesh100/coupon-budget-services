"""Business limits loaded from a versioned TOML file. No limits are hard-coded here."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_VERSIONS = frozenset({1})
SETTINGS_ENV_VAR = "SETTINGS_FILE"


class SettingsError(ValueError):
    """The settings file is missing, has an unknown version, or has a bad value."""


@dataclass(frozen=True, slots=True)
class Rules:
    version: int
    idempotency_key_ttl_seconds: int
    max_campaign_budget_micro: int
    max_coupon_face_value_micro: int


def _positive_int(section: Mapping[str, Any], key: str) -> int:
    if key not in section:
        raise SettingsError(f"missing setting: {key}")
    value = section[key]
    if type(value) is not int or value <= 0:
        raise SettingsError(f"{key} must be a positive integer, got {value!r}")
    return value


def parse_rules(data: Mapping[str, Any]) -> Rules:
    version = data.get("version")
    if type(version) is not int or version not in SUPPORTED_VERSIONS:
        raise SettingsError(f"unsupported settings version: {version!r}")
    limits = data.get("limits")
    if not isinstance(limits, Mapping):
        raise SettingsError("missing [limits] section")
    return Rules(
        version=version,
        idempotency_key_ttl_seconds=_positive_int(limits, "idempotency_key_ttl_seconds"),
        max_campaign_budget_micro=_positive_int(limits, "max_campaign_budget_micro"),
        max_coupon_face_value_micro=_positive_int(limits, "max_coupon_face_value_micro"),
    )


def load_rules(path: Path) -> Rules:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise SettingsError(f"settings file not found: {path}") from exc
    return parse_rules(data)


def load_rules_from_env(environ: Mapping[str, str]) -> Rules:
    raw = environ.get(SETTINGS_ENV_VAR, "")
    if not raw:
        raise SettingsError(f"{SETTINGS_ENV_VAR} is not set")
    return load_rules(Path(raw))

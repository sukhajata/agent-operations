"""Configuration loader — loads and validates project configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from config.schema.v1 import acap_schema, mandate_schema, mtp_schema
from schema.identity.models import MTPDocument


class ConfigValidationError(Exception):
    """Raised when project configuration fails schema validation."""


@dataclass
class MandateDefinition:
    """Exploratory agent mandate."""

    name: str
    domain: str
    polling_interval_minutes: int
    signal_threshold: float
    search_queries: list[str]


@dataclass
class ProjectConfig:
    """Validated project configuration."""

    mtp: MTPDocument
    acap_overrides: dict[str, dict[str, Any]]
    mandates: list[MandateDefinition]


def _validate(path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ConfigValidationError(f"Empty config file: {path}")
    if not isinstance(data, dict):
        raise ConfigValidationError(f"Config file must be a YAML mapping: {path}")
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        raise ConfigValidationError(
            f"Validation failed in {path.name}: {e.message} "
            f"(at {'/'.join(str(p) for p in e.absolute_path)})"
        ) from e
    return data


def _load_mandates(mandates_dir: Path) -> list[MandateDefinition]:
    if not mandates_dir.exists() or not mandates_dir.is_dir():
        return []

    mandates: list[MandateDefinition] = []
    for mandate_file in sorted(mandates_dir.glob("*.yaml")):
        data = _validate(mandate_file, mandate_schema)
        mandates.append(MandateDefinition(
            name=str(data["name"]),
            domain=str(data["domain"]),
            polling_interval_minutes=int(data["polling_interval_minutes"]),
            signal_threshold=float(data["signal_threshold"]),
            search_queries=[str(q) for q in data["search_queries"]],
        ))
    return mandates


def load_project_config(config_path: str) -> ProjectConfig:
    """Load and validate project configuration from a directory.

    Reads mtp.yaml, acap_overrides.yaml, and mandates/*.yaml,
    validates each against its JSON Schema, and returns a typed
    ProjectConfig.

    Args:
        config_path: Path to the configuration directory

    Returns:
        Validated ProjectConfig instance

    Raises:
        ConfigValidationError: If any file fails schema validation
        FileNotFoundError: If required files are missing
        ValueError: If required environment variables are missing
    """
    base = Path(config_path)

    mtp_data = _validate(base / "mtp.yaml", mtp_schema)
    mtp = MTPDocument(
        mtp_id=str(mtp_data["mtp_id"]),
        version=str(mtp_data["version"]),
        purpose=str(mtp_data["purpose"]),
        constraints=[str(c) for c in mtp_data.get("constraints", [])],
        intent_description=str(mtp_data["intent_description"]),
        created_at=mtp_data["created_at"],
        created_by=str(mtp_data["created_by"]),
    )

    acap_path = base / "acap_overrides.yaml"
    acap_overrides: dict[str, dict[str, Any]] = {}
    if acap_path.exists():
        acap_data = _validate(acap_path, acap_schema)
        agent_type = str(acap_data["agent_type"])
        acap_overrides[agent_type] = dict(acap_data)

    mandates = _load_mandates(base / "mandates")

    return ProjectConfig(
        mtp=mtp,
        acap_overrides=acap_overrides,
        mandates=mandates,
    )

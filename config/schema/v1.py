"""Version 1 configuration schemas exposed as Python dicts.

These are the versioned public configuration contracts. Changes to these
schemas require a version bump and backward-compat review.
"""

from pathlib import Path
from typing import Any

import yaml

_SCHEMA_DIR = Path(__file__).parent


def _load_yaml_schema(filename: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / filename
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Schema file {filename} must be a YAML dict")
    return data


mtp_schema: dict[str, Any] = _load_yaml_schema("mtp_schema.yaml")
acap_schema: dict[str, Any] = _load_yaml_schema("acap_schema.yaml")
mandate_schema: dict[str, Any] = _load_yaml_schema("mandate_schema.yaml")

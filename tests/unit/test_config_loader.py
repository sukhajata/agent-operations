from __future__ import annotations

from pathlib import Path

import pytest

from shared.config.loader import (
    ConfigValidationError,
    ProjectConfig,
    load_project_config,
)


@pytest.fixture
def valid_config_dir(tmp_path: Path) -> Path:
    base = tmp_path / "config"
    base.mkdir()

    (base / "mtp.yaml").write_text("""
mtp_id: mtp-v1
version: "1.0"
purpose: Improve software quality
constraints:
  - Never expose customer data
intent_description: We exist to make software better.
created_at: "2026-06-09T00:00:00Z"
created_by: admin
""")

    (base / "acap_overrides.yaml").write_text("""
acap_id: acap-exploratory
agent_type: exploratory
permitted_tools:
  - web_search
permitted_mcp_connections: []
permitted_event_types:
  - AgentSignal
  - AgentAction
forbidden_targets: []
resource_ceiling:
  max_tokens_per_run: 50000
  max_duration_seconds: 120
  max_mcp_reads_per_run: 5
""")

    mandates_dir = base / "mandates"
    mandates_dir.mkdir()
    (mandates_dir / "competitor_monitor.yaml").write_text("""
name: competitor_monitor
domain: competitive_intelligence
agent_type: free
polling_interval_minutes: 30
signal_threshold: 0.6
""")

    return base


def test_load_project_config_valid(valid_config_dir: Path) -> None:
    config = load_project_config(str(valid_config_dir))
    assert isinstance(config, ProjectConfig)
    assert config.mtp.mtp_id == "mtp-v1"
    assert config.mtp.version == "1.0"
    assert "Never expose customer data" in config.mtp.constraints
    assert len(config.mandates) == 1
    assert config.mandates[0].name == "competitor_monitor"
    assert config.mandates[0].signal_threshold == 0.6


def test_load_project_config_missing_mtp(valid_config_dir: Path) -> None:
    (valid_config_dir / "mtp.yaml").unlink()
    with pytest.raises(FileNotFoundError):
        load_project_config(str(valid_config_dir))


def test_load_project_config_invalid_mtp(valid_config_dir: Path) -> None:
    (valid_config_dir / "mtp.yaml").write_text("not_yaml: [unclosed")
    with pytest.raises(Exception):
        load_project_config(str(valid_config_dir))


def test_load_project_config_empty_mandates(valid_config_dir: Path) -> None:
    mandates_dir = valid_config_dir / "mandates"
    for f in mandates_dir.glob("*.yaml"):
        f.unlink()
    config = load_project_config(str(valid_config_dir))
    assert config.mandates == []


def test_load_project_config_focus_mandate_requires_focus_id(valid_config_dir: Path) -> None:
    (valid_config_dir / "mandates" / "competitor_monitor.yaml").write_text("""
name: competitor_monitor
domain: competitive_intelligence
agent_type: focus
polling_interval_minutes: 30
signal_threshold: 0.6
""")
    with pytest.raises(ConfigValidationError):
        load_project_config(str(valid_config_dir))


def test_load_project_config_focus_mandate_loads_focus_id(valid_config_dir: Path) -> None:
    (valid_config_dir / "mandates" / "competitor_monitor.yaml").write_text("""
name: competitor_monitor
domain: competitive_intelligence
agent_type: focus
focus_id: focus-001
polling_interval_minutes: 30
signal_threshold: 0.6
""")
    config = load_project_config(str(valid_config_dir))
    assert config.mandates[0].focus_id == "focus-001"


def test_config_validation_error_message() -> None:
    err = ConfigValidationError("test error")
    assert "test error" in str(err)


def test_mandate_definition_focus_id_default() -> None:
    from shared.config.loader import MandateDefinition
    m = MandateDefinition(
        name="test", domain="d", agent_type="free",
        polling_interval_minutes=30, signal_threshold=0.5,
    )
    assert m.focus_id is None

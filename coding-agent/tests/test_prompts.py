"""Prompt content regression tests for the coding agent.

Verifies that AGENTS.md and skill files exist, are non-empty,
and contain structural elements expected by the coding agent.
"""

from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "openhands_coding_agent"
AGENTS_MD = SRC_DIR / "AGENTS.md"
SKILLS_DIR = SRC_DIR / "skills"
MCP_CONFIG = SRC_DIR / "mcp_config.json"

EXPECTED_SKILLS = {"verify", "review", "research", "plan", "microsoft-agents"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_agents_md_exists() -> None:
    assert AGENTS_MD.exists(), "AGENTS.md missing"
    content = read(AGENTS_MD)
    assert len(content) > 100, "AGENTS.md too short"


def test_agents_md_execution_mode() -> None:
    content = read(AGENTS_MD)
    assert "Research" in content
    assert "implement" in content
    assert "PR" in content


def test_agents_md_abort_format() -> None:
    content = read(AGENTS_MD)
    assert "ABORT: INSUFFICIENT_INFORMATION" in content
    assert "ABORT: EXECUTION_FAILED" in content
    assert "ABORT: NOT_RECOMMENDED" in content


def test_agents_md_verify_review() -> None:
    content = read(AGENTS_MD)
    assert "Verify" in content


def test_agents_md_mcp_tools_section() -> None:
    content = read(AGENTS_MD)
    assert "ArcadeDB MCP Tools" in content
    assert "commitment_get" in content
    assert "commitment_complete" in content
    assert "commitment_stall" in content


def test_agents_md_completion_section() -> None:
    content = read(AGENTS_MD)
    assert "commitment_complete" in content
    assert "commitment_stall" in content


def test_agents_md_subagent_delegation() -> None:
    content = read(AGENTS_MD)
    assert "Sub-agent" in content or "Delegate" in content or "TaskToolSet" in content


def test_agents_md_non_interactive() -> None:
    content = read(AGENTS_MD)
    assert "Never ask clarifying questions" in content


# --- Skills ---


def test_skills_directory_exists() -> None:
    assert SKILLS_DIR.is_dir(), "skills/ directory missing"


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_SKILLS))
def test_skill_directory_exists(skill_name: str) -> None:
    assert (SKILLS_DIR / skill_name).is_dir(), f"skills/{skill_name}/ directory missing"


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_SKILLS))
def test_skill_md_exists(skill_name: str) -> None:
    assert (SKILLS_DIR / skill_name / "SKILL.md").exists(), f"skills/{skill_name}/SKILL.md missing"


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_SKILLS))
def test_skill_md_non_empty(skill_name: str) -> None:
    content = read(SKILLS_DIR / skill_name / "SKILL.md")
    assert len(content) > 50, f"skills/{skill_name}/SKILL.md too short"


# --- MCP Config ---


def test_mcp_config_exists() -> None:
    assert MCP_CONFIG.exists(), "mcp_config.json missing"


def test_mcp_config_has_arcadedb() -> None:
    import json
    config = json.loads(read(MCP_CONFIG))
    servers = config.get("mcpServers", {})
    assert "arcadedb" in servers, "arcadedb MCP server missing from config"

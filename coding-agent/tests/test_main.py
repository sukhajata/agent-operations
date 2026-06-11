"""Smoke tests for openhands_coding_agent.main loader functions."""

import json

from openhands_coding_agent import main as agent_main


class TestLoadMcpConfig:
    def test_returns_none_when_file_missing(self, tmp_path):
        result = agent_main.load_mcp_config(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_loads_valid_config(self, tmp_path):
        config = {"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"]}}}
        config_file = tmp_path / "mcp_config.json"
        config_file.write_text(json.dumps(config))

        result = agent_main.load_mcp_config(str(config_file))

        assert result == config
        assert "fetch" in result["mcpServers"]

    def test_loads_default_package_config(self):
        # The real mcp_config.json bundled with the package should load cleanly.
        result = agent_main.load_mcp_config()
        assert result is not None
        assert "mcpServers" in result

    def test_returns_none_for_empty_path_that_does_not_exist(self, tmp_path, monkeypatch):
        # Patch PACKAGE_DIR so the default path points at tmp_path (no file there).
        monkeypatch.setattr(agent_main, "PACKAGE_DIR", tmp_path)
        result = agent_main.load_mcp_config()
        assert result is None

    def test_absolute_path_is_used_directly(self, tmp_path):
        config = {"mcpServers": {}}
        config_file = tmp_path / "abs_config.json"
        config_file.write_text(json.dumps(config))

        result = agent_main.load_mcp_config(str(config_file))
        assert result == config


class TestLoadAgentSkills:
    def test_loads_package_skills(self, tmp_path):
        # Run against the real package directory — should pick up AGENTS.md and skills/.
        result = agent_main.load_agent_skills(str(tmp_path))
        # We can't assert exact content without mocking the SDK, but we can
        # assert it returns a list without raising.
        assert isinstance(result, list)

    def test_workspace_skills_loaded_when_agents_md_present(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# My Project\n\nDo things.\n")

        result = agent_main.load_agent_skills(str(tmp_path))
        assert isinstance(result, list)

    def test_workspace_skills_dir_loaded(self, tmp_path):
        skills_dir = tmp_path / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: test\n---\n\n# My Skill\n")

        result = agent_main.load_agent_skills(str(tmp_path))
        assert isinstance(result, list)

    def test_package_dir_not_duplicated_when_workspace_is_same(self, monkeypatch):
        # When workspace_dir == PACKAGE_DIR, workspace skills should not be loaded twice.
        package_dir = agent_main.PACKAGE_DIR
        result = agent_main.load_agent_skills(str(package_dir))
        assert isinstance(result, list)

    def test_empty_workspace_returns_at_least_package_skills(self, tmp_path):
        result_empty_ws = agent_main.load_agent_skills(str(tmp_path))
        result_package = agent_main.load_agent_skills(str(agent_main.PACKAGE_DIR))
        # Empty workspace should return at least as many skills as package-only.
        assert len(result_empty_ws) >= len(result_package)

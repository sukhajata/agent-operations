import os
from unittest.mock import patch

import pytest


def test_settings_raises_on_missing_env_vars() -> None:
    env = {k: "" for k in os.environ if not k.startswith(("UV_", "PYTHON", "HOME", "PATH"))}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="Missing required environment variables"):
            from config.env import _load_settings

            _load_settings()


def test_settings_loads_with_all_vars() -> None:
    test_env = {
        "OPENROUTER_API_KEY": "test-key",
        "ARCADEDB_URL": "http://localhost:2480",
        "ARCADEDB_USER": "root",
        "ARCADEDB_PASSWORD": "test-pass",
        "POSTGRES_URL": "postgresql://localhost/test",
        "LANGFUSE_SECRET_KEY": "sk-lf-test",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
        "LANGFUSE_HOST": "https://cloud.langfuse.com",
        "AGENT_OPERATIONS_CONFIG_PATH": "./config/reference",
        "RENDER_API_KEY": "rnd-test",
    }
    with patch.dict(os.environ, test_env, clear=True):
        from config.env import _load_settings

        settings = _load_settings()
        assert settings.openrouter_api_key == "test-key"
        assert settings.arcadedb_url == "http://localhost:2480"

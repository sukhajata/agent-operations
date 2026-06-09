import os


def pytest_sessionstart() -> None:
    os.environ.setdefault("OPENROUTER_API_KEY", "sk-test-key")
    os.environ.setdefault("ARCADEDB_URL", "http://localhost:2480")
    os.environ.setdefault("ARCADEDB_USER", "test-user")
    os.environ.setdefault("ARCADEDB_PASSWORD", "test-password")
    os.environ.setdefault("POSTGRES_URL", "postgresql://localhost:5432/test")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-lf-test")
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    os.environ.setdefault("LANGFUSE_HOST", "https://localhost")
    os.environ.setdefault("AGENT_OPERATIONS_CONFIG_PATH", "./config/reference")
    os.environ.setdefault("RENDER_API_KEY", "rnd-test-key")

from pydantic import ValidationError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str
    arcadedb_url: str
    arcadedb_user: str
    arcadedb_password: str
    postgres_url: str
    langfuse_secret_key: str
    langfuse_public_key: str
    langfuse_host: str
    agent_operations_config_path: str
    render_api_key: str


def _load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as e:
        missing = [err["loc"][0] for err in e.errors() if err["type"] == "missing"]
        names = ", ".join(str(m).upper() for m in missing)
        raise ValueError(f"Missing required environment variables: {names}") from e


settings = _load_settings()

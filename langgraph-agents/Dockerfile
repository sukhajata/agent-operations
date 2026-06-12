# Build with: docker build --platform linux/arm64 -f Dockerfile .
# LangGraph agents platform image

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Python package
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY agents/ ./agents/
COPY shared/ ./shared/
COPY schema/ ./schema/
COPY config/ ./config/
COPY tools/ ./tools/

RUN uv sync --frozen --no-dev

RUN useradd -m -u 1000 agent
USER agent
WORKDIR /workspace

# Overridden per Render service
CMD ["echo", "Override CMD per service"]

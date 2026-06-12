# Build with: docker build --platform linux/arm64 -f Dockerfile .
# Standalone coding agent image for the OpenHands SDK

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux git curl ca-certificates gnupg libicu72 \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g typescript ts-node

# .NET SDK 9
COPY --from=mcr.microsoft.com/dotnet/sdk:9.0-bookworm-slim /usr/share/dotnet /usr/share/dotnet
RUN ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet
ENV DOTNET_ROOT=/usr/share/dotnet

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

# Playwright Chromium
RUN /app/.venv/bin/python -m playwright install chromium --with-deps \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 agent
USER agent
WORKDIR /workspace

ENTRYPOINT ["uv", "run", "--project", "/app", "coding-agent"]

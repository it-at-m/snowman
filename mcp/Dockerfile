FROM registry.access.redhat.com/ubi10/ubi-minimal:latest@sha256:d801168f5e8b108586c27a4fd5c92e3c1e8d061084383713926e2ca61b8b6c64

WORKDIR /app

ARG UV_HTTP_TIMEOUT=300
ARG UV_HTTP_RETRIES=10
ARG UV_PYTHON_INSTALL_MIRROR
ARG IMAGE_CREATED="unknown"
ARG IMAGE_REVISION="unknown"
ARG IMAGE_VERSION="unknown"

ENV UV_HTTP_TIMEOUT=$UV_HTTP_TIMEOUT \
    UV_HTTP_RETRIES=$UV_HTTP_RETRIES \
    UV_PYTHON_INSTALL_MIRROR=$UV_PYTHON_INSTALL_MIRROR \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest@sha256:440fd6477af86a2f1b38080c539f1672cd22acb1b1a47e321dba5158ab08864d /uv /uvx /bin/

USER root

COPY pyproject.toml uv.lock README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --locked --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --locked && \
    mkdir -p /app/model_cache && \
    chgrp -R 0 /app && \
    chmod -R g+rwX /app

LABEL org.opencontainers.image.authors='Landeshauptstadt Muenchen <opensource@muenchen.de>' \
    org.opencontainers.image.vendor='Landeshauptstadt Muenchen' \
    org.opencontainers.image.created="$IMAGE_CREATED" \
    org.opencontainers.image.revision="$IMAGE_REVISION" \
    org.opencontainers.image.version="$IMAGE_VERSION" \
    org.opencontainers.image.source='https://github.com/it-at-m/snowman' \
    org.opencontainers.image.title='snow-search-mcp' \
    org.opencontainers.image.description='MCP server for Service Now knowledge retrieval.'

USER 1001

ENV PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    MCP_PATH=/mcp \
    FASTEMBED_CACHE_PATH=/app/model_cache \
    TQDM_DISABLE=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    PYTHONWARNINGS=ignore \
    APP_VERSION=${IMAGE_VERSION}

EXPOSE 8080

ENTRYPOINT ["python", "-m", "src.main"]

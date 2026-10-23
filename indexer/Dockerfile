FROM registry.access.redhat.com/ubi10/ubi-minimal:latest@sha256:ab67cd02caf8706e34a695a1432ebe965934f6128ec352a6c3f4048b43a4fb5e

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

COPY --from=ghcr.io/astral-sh/uv:latest@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/

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
    org.opencontainers.image.title='snow-search-indexer' \
    org.opencontainers.image.description='Indexer for ServiceNow knowledge documents into Qdrant.'

USER 1001

ENV PATH="/app/.venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/app/model_cache \
    TQDM_DISABLE=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    PYTHONWARNINGS=ignore \
    APP_VERSION=${IMAGE_VERSION}

ENTRYPOINT ["python", "-m", "src.main"]

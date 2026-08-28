# snow-search

This repository contains two Python projects and shared repository-level tooling.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `indexer/` | Source-independent indexing pipeline for canonical documents, with ServiceNow as an example adapter. |
| `mcp/` | Python project for the MCP server used for retrieval over Qdrant. |
| `infrastructure/` | Helm umbrella chart setup for Qdrant and the MCP server. The indexer chart entry is kept disabled until its deployment is ready. |
| `.gitlab-ci.yml` | Repository-level CI pipeline configuration for snow-search. |
| `.pre-commit-config.yaml` | Repository-level pre-commit hook configuration. |
| `ruff.toml` | Shared Ruff linting and formatting configuration for both Python projects. |
| `pyproject.toml` | Root uv project for shared development tooling only. It is not an application package. |

The previous PoC has been removed from the active repository structure. MCP testing can be rebuilt later against the dedicated `mcp/` project.

Both Python projects keep their standard utility modules for logging, environment variable handling, and version reporting inside their own package:

- `indexer/src/utils/`
- `mcp/src/utils/`

## Python Environments

Both application projects have their own `pyproject.toml` and should be treated as separate Python environments. Keep project-specific `.env` files inside the relevant project directory and use the matching `.env.example` as the template.

Create or sync the indexer environment:

```bash
uv sync --project indexer
```

Create or sync the MCP environment:

```bash
uv sync --project mcp
```

Run the indexer project entry point:

```bash
uv run --directory indexer python -m src.main
```

Run the MCP project entry point:

```bash
uv run --project mcp python -m src.main
```

## Shared Tooling

Repository-level tooling remains at the repository root because it applies to both Python projects.

Sync the root tooling environment:

```bash
uv sync
```

Install pre-commit hooks:

```bash
uv run pre-commit install
```

Run pre-commit manually:

```bash
uv run pre-commit run --all-files
```

Run Ruff linting:

```bash
uv run ruff check .
```

Run Ruff formatting:

```bash
uv run ruff format .
```

## Infrastructure

The `infrastructure/` area currently deploys:

- Qdrant deployed via the imported `Qdrant-Helm.gitlab-ci.yml` template and `values-qdrant-*.yaml`
- the MCP server via the local `pyarch` OpenShift chart

The `indexer` CronJob values are present but disabled by default. Enable them explicitly once its container build and runtime setup are ready.

Render the dev setup locally:

```bash
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update
helm template qdrant qdrant/qdrant --values values-qdrant-dev.yaml
helm template qdrant qdrant/qdrant --values values-qdrant-test.yaml

# Optional local umbrella chart render
helm dependency build infrastructure/charts/snow-search
helm template snow-search-dev infrastructure/charts/snow-search -f infrastructure/values-snow-search-dev.yaml
helm template snow-search-test infrastructure/charts/snow-search -f infrastructure/values-snow-search-test.yaml
```

Build the MCP image from the MCP project directory:

```bash
docker build -t snow-search-mcp:latest mcp
```

[uv]: https://docs.astral.sh/uv/
[ruff]: https://docs.astral.sh/ruff/
[pre-commit]: https://pre-commit.com/

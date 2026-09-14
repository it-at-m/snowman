# snow-search

This repository contains two Python projects and shared repository-level tooling.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `indexer/` | Source-independent indexing pipeline for canonical documents, with ServiceNow as an example adapter. |
| `mcp/` | Python project for the MCP server used for retrieval over Qdrant. |
| `.pre-commit-config.yaml` | Repository-level pre-commit hook configuration. |
| `ruff.toml` | Shared Ruff linting and formatting configuration for both Python projects. |
| `pyproject.toml` | Root uv project for shared development tooling only. It is not an application package. |


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

[uv]: https://docs.astral.sh/uv/
[ruff]: https://docs.astral.sh/ruff/
[pre-commit]: https://pre-commit.com/

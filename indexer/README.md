# Generic Qdrant Indexer

This project supplies the reusable indexing half of the RAG template. It owns document validation, splitting, dense or hybrid embedding, Qdrant collection validation, batched upserts, and safe removal of stale points.

Template users only implement acquisition and source-specific conversion. The included ServiceNow loader is a working example.

## Source adapter contract

Implement `DocumentSource.load_documents()` and return a complete snapshot of LangChain `Document` objects:

```python
from collections.abc import Iterable
from langchain_core.documents import Document

class MySource:
    def load_documents(self) -> Iterable[Document]:
        yield Document(
            id='stable-source-id',
            page_content='Canonical plain text or Markdown',
            metadata={'source': 'https://example.invalid/item'},
        )
```

Each document needs a stable, unique `id`, non-empty `page_content`, and JSON-compatible metadata. The `_index` metadata key is reserved. Replace the `SnowLoader` composition in `src/main.py` with the new adapter; the pipeline itself does not change.

One run must return the complete authoritative snapshot for one collection. If several sources share a collection, combine them behind one source adapter and run the pipeline once.

## Synchronization behavior

Chunks receive deterministic point IDs and the current run ID. Only after acquisition and every upload completes does the pipeline delete points from older runs. A failed run therefore never performs stale-point deletion.

An empty snapshot fails safely by default. Set `ALLOW_EMPTY_SNAPSHOT=true` only when an empty source should deliberately clear the collection.

Existing collections are validated against the configured dense/hybrid mode and vector names. Incompatible collections fail with an error and are never recreated automatically.

## Setup and execution

Copy `.env.example` to `.env`, provide the Qdrant, embedding, and source credentials, then run:

Non-secret settings can alternatively be stored in `indexer/config.yaml`. Copy
`config.example.yaml` to `config.yaml` to get started. It contains separate
`indexer` and `servicenow` sections. Set `SNOWMAN_CONFIG_FILE` to load a file
from another path.

Environment variables and `.env` values override YAML, so credentials should
remain in environment variables or mounted secrets rather than committed YAML.
The configuration is loaded once when the indexer starts.

```bash
uv sync --project indexer
uv run --directory indexer python -m src.main
```

The indexer accepts `VDB_COLLECTION_NAME`. For compatibility with the MCP configuration, a single value in `VDB_COLLECTIONS` is also accepted; comma-separated collections are rejected by the indexer.

## ServiceNow loader

Set `SERVICENOW_URL` to the complete Knowledge API endpoint, including the knowledge-base selector:

```dotenv
SERVICENOW_URL=https://example.service-now.com/api/sn_km_api/knowledge/articles?kb=knowledge-base-sys-id
SERVICENOW_CLIENT_ID=...
SERVICENOW_CLIENT_SECRET=...
```

The loader follows pagination until every published article has been read, fetches each article's full content, and converts its HTML to Markdown. Each LangChain document includes a `scope` metadata value of `user`, `admin`, or `general`, derived from `meta_description`. Articles mentioning both users and administrators are `general`. ServiceNow attachments are kept as links in the `attachments` metadata value and are not downloaded or parsed.

Run verification from this directory:

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check src tests
```

# snow-search MCP Server

Python project for the snow-search MCP server. One server can expose multiple
topic-specific search tools while sharing the same retriever, Qdrant client,
embedding models, reranker, and collections.

## Environment

Sync the project environment from the repository root:

```bash
uv sync --project mcp
```

Project-specific environment variables belong in `mcp/.env`. Use `mcp/.env.example` as the template.

Non-secret settings can also be stored in `mcp/config.yaml`. Copy
`config.example.yaml` to `config.yaml` to get started. The file has separate
`mcp` and `retrieval` sections. Set `SNOWMAN_CONFIG_FILE` to use a different
path, for example a ConfigMap mount in OpenShift.

Constructor arguments, environment variables, and `.env` values override YAML.
Keep credentials such as API keys in environment variables or mounted secrets;
do not commit them to YAML. Configuration is read at startup, so restart the
server after changing the file.

Relevant MCP defaults:

| Variable              | Default                    | Purpose                                                                 |
| --------------------- | -------------------------- | ----------------------------------------------------------------------- |
| `MCP_TRANSPORT`       | `streamable-http`          | MCP transport for the process.                                          |
| `MCP_HOST`            | `127.0.0.1`                | Bind host for HTTP transport. Use `0.0.0.0` in containers.              |
| `MCP_PORT`            | `8080`                     | Bind port, aligned with the Helm service values.                        |
| `MCP_PATH`            | `/mcp`                     | Streamable HTTP MCP endpoint.                                           |
| `MCP_ALLOWED_HOSTS`   | local hosts for `MCP_PORT` | Comma-separated Host headers allowed by transport security.             |
| `MCP_ALLOWED_ORIGINS` | empty                      | Comma-separated browser origins, only needed for browser-based clients. |

## Retrieval Tools and Scoping

Retrieval tools are created from configuration when the server starts. Each tool
accepts only a self-contained `query`; callers cannot supply a metadata filter or
retrieval profile. The tool selected by an assistant determines the
server-controlled Qdrant filter.

`VDB_FILTER_BASE_CONDITIONS` is a JSON array of conditions applied to every tool:

```json
[
  {"field": "metadata.source_id", "values": ["snow-kb"]}
]
```

`VDB_RETRIEVAL_TOOLS` is a JSON array of generated tool definitions:

```json
[
  {
    "name": "search_snow_knowledge_base",
    "title": "Search SNOW knowledge base",
    "description": "Search generally available SNOW articles.",
    "conditions": []
  },
  {
    "name": "search_eakte_knowledge_base",
    "title": "Search E-Akte knowledge base",
    "description": "Search E-Akte articles.",
    "conditions": [
      {"field": "metadata.topic", "values": ["eakte"]},
      {
        "field": "metadata.knowledgebase",
        "values": ["general", "key_user"]
      }
    ]
  }
]
```

Base conditions and all conditions within a tool are combined with `AND`.
Multiple values within one condition are combined with `OR`. Field paths and
values use exact Qdrant payload matches, so they must already exist in indexed
documents with the same spelling and casing.

Select the individual generated MCP tool in each assistant's custom toolset. To
add another topic, confirm its existing Qdrant metadata, add another tool entry,
restart or roll out this same MCP deployment, and select the new tool for the
assistant. No Python function or separate MCP deployment is needed.

This filtering scopes retrieval for relevance; it is not authorization. Only
advertise scopes whose matching documents are safe for every user who can attach
or invoke the tool. Restricted content requires trusted caller identity and an
independent authorization check.

## Run

Start the server locally:

```bash
uv run --project mcp python -m src.main
```

Default local endpoints:

- MCP endpoint: `http://127.0.0.1:8080/mcp`
- Health endpoint: `http://127.0.0.1:8080/healthz`

For local stdio experiments, set `MCP_TRANSPORT=stdio`. Logging is written to stderr so stdout remains available for the MCP protocol.

## Deployment Notes

The OpenShift service values already use port `8080`. Keep external routes disabled until the intended agent/runtime and authentication model are known. When exposing the MCP endpoint remotely, configure exact `MCP_ALLOWED_HOSTS` and, for browser clients, `MCP_ALLOWED_ORIGINS`.

### Host Header Protection

The MCP Streamable HTTP transport enables DNS rebinding protection by default. For every request to `MCP_PATH`, the server checks the HTTP `Host` header against `MCP_ALLOWED_HOSTS`.

If OpenShift exposes the service through a route such as:

```text
snow-mcp-server-snow-semantic-squirrel-dev.apps.test.capk.muenchen.de
```

then that exact host must be listed in `MCP_ALLOWED_HOSTS`. Otherwise the server rejects MCP requests with:

```text
Invalid Host header: <route-host>
POST /mcp HTTP/1.1" 421 Misdirected Request
```

Health probes can still return `200 OK` while MCP requests fail, because `/healthz` is a custom health route and the host check is applied by the MCP transport path. When adding or changing an OpenShift route, update the environment-specific Helm values with the exact external host and restart the pod so the new environment variable is loaded.

The project keeps the standard utility modules in `src/utils/`:

- `envtools.py`
- `logtools.py`
- `version.py`

## Tests

```bash
cd mcp
uv run python -m unittest discover -s tests
uv run ruff check .
uv run ruff format --check .
```

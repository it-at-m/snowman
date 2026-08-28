# snow-search MCP Server

Python project for the snow-search MCP server.

The server is intentionally minimal for now: it exposes the MCP protocol via Streamable HTTP and provides a basic health endpoint. Tools, resources, prompts, and domain logic will be added later.

## Environment

Sync the project environment from the repository root:

```bash
uv sync --project mcp
```

Project-specific environment variables belong in `mcp/.env`. Use `mcp/.env.example` as the template.

Relevant MCP defaults:

| Variable              | Default                    | Purpose                                                                 |
| --------------------- | -------------------------- | ----------------------------------------------------------------------- |
| `MCP_TRANSPORT`       | `streamable-http`          | MCP transport for the process.                                          |
| `MCP_HOST`            | `127.0.0.1`                | Bind host for HTTP transport. Use `0.0.0.0` in containers.              |
| `MCP_PORT`            | `8080`                     | Bind port, aligned with the Helm service values.                        |
| `MCP_PATH`            | `/mcp`                     | Streamable HTTP MCP endpoint.                                           |
| `MCP_ALLOWED_HOSTS`   | local hosts for `MCP_PORT` | Comma-separated Host headers allowed by transport security.             |
| `MCP_ALLOWED_ORIGINS` | empty                      | Comma-separated browser origins, only needed for browser-based clients. |

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
```

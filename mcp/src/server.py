from typing import Annotated

from langchain_core.documents import Document
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config.settings import McpSettings, RetrievalSettings, RetrievalToolSettings
from src.retrieval.filters import build_retrieval_filter
from src.retrieval.retriever import Retriever

_METADATA_FIELDS = ("number", "title", "source", "knowledgebase", "lang", "updated_at")


def _serialize_documents(
    documents_by_collection: dict[str, list[Document]],
) -> list[dict[str, object]]:
    """Project retrieved documents to the stable MCP response shape."""
    results = [
        {
            "page_content": document.page_content,
            **{field: document.metadata[field] for field in _METADATA_FIELDS if field in document.metadata},
            "relevance_score": round(
                float(document.metadata.get("relevance_score", 0.0)),
                3,
            ),
        }
        for documents in documents_by_collection.values()
        for document in documents
    ]
    results.sort(key=lambda result: result["relevance_score"], reverse=True)
    return results


def create_server(
    settings: McpSettings | None = None,
    retrieval_settings: RetrievalSettings | None = None,
) -> FastMCP:
    settings = settings or McpSettings()
    retrieval_settings = retrieval_settings or RetrievalSettings()
    retriever = Retriever(retrieval_settings)

    server = FastMCP(
        name="snow-search-mcp",
        instructions="MCP server for retrieval over Qdrant.",
        host=settings.host,
        port=settings.port,
        streamable_http_path=settings.path,
        log_level=settings.log_level,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=settings.dns_rebinding_protection,
            allowed_hosts=settings.allowed_hosts_list,
            allowed_origins=settings.allowed_origins_list,
        ),
    )

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "snow-search-mcp"})

    def create_search_handler(tool_config: RetrievalToolSettings):
        # Filters are immutable server configuration, so build each one once at
        # startup rather than accepting filter details from the MCP caller.
        qdrant_filter = build_retrieval_filter(
            retrieval_settings.filter_base_conditions,
            tool_config,
        )

        def search(
            query: Annotated[
                str,
                Field(
                    min_length=1,
                    description=("Self-contained search query using terminology likely to appear in the company knowledge base."),
                ),
            ],
        ) -> list[dict[str, object]]:
            documents_by_collection = retriever.retrieve_documents(
                query,
                filter=qdrant_filter,
            )
            return _serialize_documents(documents_by_collection)

        return search

    # The factory above avoids Python's late-binding loop behavior: every handler
    # keeps the filter belonging to the tool it was created for.
    for tool_config in retrieval_settings.retrieval_tools:
        server.tool(
            name=tool_config.name,
            title=tool_config.title,
            description=tool_config.description,
        )(create_search_handler(tool_config))

    return server

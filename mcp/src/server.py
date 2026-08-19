from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from qdrant_client import models
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config.settings import McpSettings, RetrievalSettings
from src.retrieval.retriever import Retriever


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

    _METADATA_FIELDS = ("number", "title", "source", "knowledgebase", "lang", "updated_at")
    @server.tool()
    def search_eakte_knowledge_base(
        query: Annotated[
            str,
            Field(
                description=(
                    "Search query in German. Use knowledge base terminology "
                    "(e.g. 'Sachakte EAP1 Betreffseinheit anlegen', not 'how do I "
                    "make a new file'). Include the function, document type, or "
                    "process step. Must be self-contained: resolve references from "
                    "the conversation first."
                )
            ),
        ],
    ) -> list[dict[str, object]]:
        """Search the ServiceNow knowledge base for E-Akte articles matching the query.

        This is the only source of E-Akte information. Call it before answering any
        question about E-Akte processes, functions, retention, or permissions.

        Call again with a reformulated query if results are empty or only partly
        relevant — a second search is cheap. Vary the terminology rather than
        repeating the same query.

        Returns article chunks ordered by relevance. Each chunk has:
        - page_content: article text. May itself contain Markdown links to
            Anleitungen (PDFs) and interactive tutorials. These links are part of
            the source and may be cited.
        - number: the KB number, e.g. "KB0017236". Cite this.
        - title: article title.
        - source: canonical article URL.
        - knowledgebase: the audience this article was written for, e.g.
            "Anwender*innen". Prefer articles matching the user's role when several
            articles conflict.
        - lang: article language.
        - updated_at: last modification. Indicates recency only — a newer article
            does not supersede an older one.
        - relevance_score: 0–1 semantic similarity. Comparative only; a high score
            does not mean the chunk answers the question.

        Several chunks may share the same `number` — they are parts of one article.
        Cite that article once.

        An empty result means the knowledge base contains nothing relevant. It does
        not mean the answer is obvious or can be supplied from general knowledge.
        """
        qdrant_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.source_id",
                    match=models.MatchValue(value="snow-kb"),
                )
            ]
        )
        documents_by_collection = retriever.retrieve_documents(query, filter=qdrant_filter)

        results = [
            {
                "page_content": document.page_content,
                **{
                    field: document.metadata[field]
                    for field in _METADATA_FIELDS
                    if field in document.metadata
                },
                "relevance_score": round(
                    float(document.metadata.get("relevance_score", 0.0)), 3
                ),
            }
            for documents in documents_by_collection.values()
            for document in documents
        ]
        results.sort(key=lambda r: r["relevance_score"], reverse=True)
        return results

    return server

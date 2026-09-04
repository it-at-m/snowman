import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from qdrant_client import models
from src.config.settings import McpSettings, RetrievalSettings
from src.server import create_server


class FakeRetriever:
    instances: list["FakeRetriever"] = []

    def __init__(self, _settings) -> None:
        self.calls: list[tuple[str, models.Filter | None]] = []
        self.instances.append(self)

    def retrieve_documents(
        self,
        query: str,
        filter: models.Filter | None = None,
    ) -> dict[str, list[Document]]:
        self.calls.append((query, filter))
        return {
            "first": [
                Document(
                    page_content=f"less relevant answer for {query}",
                    metadata={
                        "number": "KB-low",
                        "source": "https://example.org/low",
                        "relevance_score": 0.1236,
                        "internal": "not exposed",
                    },
                )
            ],
            "second": [
                Document(
                    page_content=f"best answer for {query}",
                    metadata={"number": "KB-high", "relevance_score": 0.9876},
                )
            ],
        }


class ServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeRetriever.instances.clear()

    @staticmethod
    def retrieval_settings() -> RetrievalSettings:
        return RetrievalSettings(
            _env_file=None,
            filter_base_conditions=[
                {"field": "metadata.source_id", "values": ["snow-kb"]},
                {"field": "metadata.visibility", "values": ["public"]},
            ],
            retrieval_tools=[
                {
                    "name": "search_snow_knowledge_base",
                    "title": "Search SNOW knowledge base",
                    "description": "Search generally available SNOW articles.",
                    "conditions": [],
                },
                {
                    "name": "search_eakte_knowledge_base",
                    "title": "Search E-Akte knowledge base",
                    "description": "Search E-Akte articles.",
                    "conditions": [{"field": "metadata.topic", "values": ["eakte"]}],
                },
                {
                    "name": "search_personalwesen_knowledge_base",
                    "title": "Search Personalwesen knowledge base",
                    "description": "Search personnel articles.",
                    "conditions": [{"field": "metadata.topic", "values": ["personalwesen"]}],
                },
            ],
        )

    def test_creates_streamable_http_app_with_mcp_and_health_routes(self) -> None:
        settings = McpSettings(_env_file=None, path="/mcp-test", port=9090)

        with patch("src.server.Retriever", FakeRetriever):
            server = create_server(settings, self.retrieval_settings())
        app = server.streamable_http_app()
        paths = {route.path for route in app.routes}

        self.assertIn("/mcp-test", paths)
        self.assertIn("/healthz", paths)
        self.assertEqual(9090, server.settings.port)
        self.assertEqual("/mcp-test", server.settings.streamable_http_path)

    async def test_registers_every_configured_tool_with_query_only_schema(self) -> None:
        settings = McpSettings(_env_file=None)
        retrieval_settings = self.retrieval_settings()

        with patch("src.server.Retriever", FakeRetriever):
            server = create_server(settings, retrieval_settings)
            tools = await server.list_tools()

        tools_by_name = {tool.name: tool for tool in tools}
        self.assertEqual(
            {tool.name for tool in retrieval_settings.retrieval_tools},
            set(tools_by_name),
        )
        for tool_config in retrieval_settings.retrieval_tools:
            tool = tools_by_name[tool_config.name]
            self.assertEqual(tool_config.title, tool.title)
            self.assertEqual(tool_config.description, tool.description)
            self.assertEqual({"query"}, set(tool.inputSchema["properties"]))
            self.assertEqual(["query"], tool.inputSchema["required"])

    async def test_each_tool_uses_its_own_filter_on_the_shared_retriever(self) -> None:
        with patch("src.server.Retriever", FakeRetriever):
            server = create_server(
                McpSettings(_env_file=None),
                self.retrieval_settings(),
            )

            for tool_name in (
                "search_snow_knowledge_base",
                "search_eakte_knowledge_base",
                "search_personalwesen_knowledge_base",
            ):
                await server.call_tool(tool_name, {"query": "access"})

        self.assertEqual(1, len(FakeRetriever.instances))
        calls = FakeRetriever.instances[0].calls
        self.assertEqual(3, len(calls))

        fields_by_call = [[condition.key for condition in qdrant_filter.must] for _, qdrant_filter in calls]
        self.assertEqual(
            [
                ["metadata.source_id", "metadata.visibility"],
                ["metadata.source_id", "metadata.visibility", "metadata.topic"],
                ["metadata.source_id", "metadata.visibility", "metadata.topic"],
            ],
            fields_by_call,
        )
        self.assertEqual("eakte", calls[1][1].must[-1].match.value)
        self.assertEqual("personalwesen", calls[2][1].must[-1].match.value)

    async def test_results_keep_projection_rounding_and_descending_sort(self) -> None:
        with patch("src.server.Retriever", FakeRetriever):
            server = create_server(
                McpSettings(_env_file=None),
                self.retrieval_settings(),
            )
            result = await server.call_tool(
                "search_snow_knowledge_base",
                {"query": "PM tools"},
            )

        serialized = result[1]["result"]
        self.assertEqual(["KB-high", "KB-low"], [item["number"] for item in serialized])
        self.assertEqual([0.988, 0.124], [item["relevance_score"] for item in serialized])
        self.assertNotIn("internal", serialized[1])
        self.assertEqual("https://example.org/low", serialized[1]["source"])


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import patch

from src.config.settings import McpSettings
from src.server import create_server
from langchain_core.documents import Document


class FakeRetriever:
    def __init__(self, _settings) -> None:
        self.calls = 0

    def retrieve_documents(self, query: str) -> dict[str, list[Document]]:
        self.calls += 1
        return {
            "info": [
                Document(
                    page_content=f"answer for {query}",
                    metadata={"source": "confluence"},
                )
            ]
        }


class ServerTests(unittest.IsolatedAsyncioTestCase):
    def test_creates_streamable_http_app_with_mcp_and_health_routes(self) -> None:
        settings = McpSettings(_env_file=None, path="/mcp-test", port=9090)

        with patch("src.server.Retriever", FakeRetriever):
            server = create_server(settings)
        app = server.streamable_http_app()
        paths = {route.path for route in app.routes}

        self.assertIn("/mcp-test", paths)
        self.assertIn("/healthz", paths)
        self.assertEqual(9090, server.settings.port)
        self.assertEqual("/mcp-test", server.settings.streamable_http_path)

    async def test_registers_retrieve_documents_tool(self) -> None:
        settings = McpSettings(_env_file=None)

        with patch("src.server.Retriever", FakeRetriever):
            server = create_server(settings)
            tools = await server.list_tools()

            self.assertIn("retrieve_documents", {tool.name for tool in tools})

            result = await server.call_tool("retrieve_documents", {"query": "PM tools"})

        self.assertEqual(
            {
                "info": [
                    {
                        "page_content": "answer for PM tools",
                        "metadata": {"source": "confluence"},
                    }
                ]
            },
            json.loads(result[0][0].text),
        )


if __name__ == "__main__":
    unittest.main()

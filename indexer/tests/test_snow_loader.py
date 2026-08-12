import unittest

from langchain_core.documents import Document
from src.config.settings import SnowSettings
from src.loaders.snow_loader import SnowLoader


class FakeSnowLoader(SnowLoader):
    def _fetch_articles(self):
        return [
            Document(
                id="stable-id",
                page_content="<h1>Title</h1><p>Body</p>",
                metadata={"source": "https://example.invalid/article"},
            )
        ]


class SnowLoaderTests(unittest.TestCase):
    def test_conversion_preserves_stable_id_and_metadata(self):
        settings = SnowSettings(
            _env_file=None,
            servicenow_url="https://example.invalid",
            servicenow_client_id="client",
            servicenow_client_secret="secret",
        )
        document = FakeSnowLoader(settings).load_documents()[0]

        self.assertEqual("stable-id", document.id)
        self.assertIn("# Title", document.page_content)
        self.assertEqual("https://example.invalid/article", document.metadata["source"])


if __name__ == "__main__":
    unittest.main()

import unittest

from langchain_core.documents import Document
from src.config.settings import RetrievalSettings
from src.retrieval.retriever import Retriever


class FakeVectorStoreRetriever:
    def __init__(self, collection: str) -> None:
        self.collection = collection

    def invoke(self, query: str) -> list[Document]:
        return [Document(page_content=f"{self.collection}: {query}", metadata={"collection": self.collection})]


class FakeRetriever(Retriever):
    def _build_retriever(self, collection: str | None = None):
        return FakeVectorStoreRetriever(collection or self.config.collections_list[0])


class RetrieverTests(unittest.TestCase):
    def test_retrieve_documents_searches_each_configured_collection(self) -> None:
        settings = RetrievalSettings(_env_file=None, collections="info,service")
        retriever = FakeRetriever(settings)

        result = retriever.retrieve_documents(" Frage ")

        self.assertEqual(["info", "service"], list(result.keys()))
        self.assertEqual("info: Frage", result["info"][0].page_content)
        self.assertEqual("service: Frage", result["service"][0].page_content)

    def test_retrieve_documents_rejects_empty_query(self) -> None:
        retriever = FakeRetriever(RetrievalSettings(_env_file=None))

        with self.assertRaises(ValueError):
            retriever.retrieve_documents("   ")


if __name__ == "__main__":
    unittest.main()

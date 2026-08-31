import unittest

from langchain_core.documents import Document
from qdrant_client import models
from src.config.settings import RetrievalSettings
from src.retrieval.retriever import Retriever


class FakeVectorStoreRetriever:
    def __init__(self, collection: str, search_kwargs: dict[str, object]) -> None:
        self.collection = collection
        self.search_kwargs = search_kwargs

    def invoke(self, query: str) -> list[Document]:
        return [Document(page_content=f"{self.collection}: {query}", metadata={"collection": self.collection})]


class FakeVectorStore:
    def __init__(self, collection: str) -> None:
        self.collection = collection
        self.search_kwargs_calls: list[dict[str, object]] = []

    def as_retriever(
        self,
        *,
        search_type: str,
        search_kwargs: dict[str, object],
    ) -> FakeVectorStoreRetriever:
        if search_type != "similarity_score_threshold":
            raise AssertionError(f"unexpected search type: {search_type}")
        self.search_kwargs_calls.append(search_kwargs)
        return FakeVectorStoreRetriever(self.collection, search_kwargs)


class FakeRetriever(Retriever):
    def __init__(self, config: RetrievalSettings) -> None:
        self.build_counts: dict[str, int] = {}
        self.stores: dict[str, FakeVectorStore] = {}
        super().__init__(config)

    def _build_vectorstore(self, collection: str | None = None) -> FakeVectorStore:
        collection_name = collection or self.config.collections_list[0]
        self.build_counts[collection_name] = self.build_counts.get(collection_name, 0) + 1
        store = FakeVectorStore(collection_name)
        self.stores[collection_name] = store
        return store


class RetrieverTests(unittest.TestCase):
    def test_retrieve_documents_searches_each_configured_collection(self) -> None:
        settings = RetrievalSettings(
            _env_file=None,
            collections="info,service",
            retrieval_final_n_docs=10,
        )
        retriever = FakeRetriever(settings)
        qdrant_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.topic",
                    match=models.MatchValue(value="eakte"),
                )
            ]
        )

        result = retriever.retrieve_documents(" Frage ", filter=qdrant_filter)

        self.assertEqual(["info", "service"], list(result.keys()))
        self.assertEqual("info: Frage", result["info"][0].page_content)
        self.assertEqual("service: Frage", result["service"][0].page_content)
        for store in retriever.stores.values():
            self.assertIs(qdrant_filter, store.search_kwargs_calls[0]["filter"])

    def test_consecutive_filters_do_not_share_request_state(self) -> None:
        retriever = FakeRetriever(RetrievalSettings(_env_file=None))
        first_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.topic",
                    match=models.MatchValue(value="eakte"),
                )
            ]
        )
        second_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.topic",
                    match=models.MatchValue(value="personalwesen"),
                )
            ]
        )

        retriever.retrieve_documents("access", filter=first_filter)
        retriever.retrieve_documents("access", filter=second_filter)

        calls = retriever.stores["snow-search"].search_kwargs_calls
        self.assertIs(first_filter, calls[0]["filter"])
        self.assertIs(second_filter, calls[1]["filter"])
        self.assertIsNot(calls[0], calls[1])

    def test_vectorstores_are_cached_per_collection(self) -> None:
        settings = RetrievalSettings(
            _env_file=None,
            collections="info,service",
            retrieval_final_n_docs=10,
        )
        retriever = FakeRetriever(settings)

        retriever.retrieve_documents("first")
        retriever.retrieve_documents("second")

        self.assertEqual({"info": 1, "service": 1}, retriever.build_counts)
        self.assertEqual(2, len(retriever.stores["info"].search_kwargs_calls))
        self.assertEqual(2, len(retriever.stores["service"].search_kwargs_calls))

    def test_retrieve_documents_rejects_empty_query(self) -> None:
        retriever = FakeRetriever(RetrievalSettings(_env_file=None))

        with self.assertRaises(ValueError):
            retriever.retrieve_documents("   ")

        self.assertEqual({}, retriever.build_counts)

    def test_interleaving_preserves_list_order_and_final_limit(self) -> None:
        first = [Document(page_content="a1"), Document(page_content="a2")]
        second = [Document(page_content="b1"), Document(page_content="b2")]

        result = Retriever.interleave_document_lists([first, second], n_final=3)

        self.assertEqual(["a1", "b1", "a2"], [document.page_content for document in result])


if __name__ == "__main__":
    unittest.main()

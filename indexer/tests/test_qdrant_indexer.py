import hashlib
import unittest

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant.sparse_embeddings import SparseEmbeddings, SparseVector
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from src.config.settings import IndexerSettings
from src.indexer.qdrant_indexer import QdrantIndexer


class FakeEmbeddings(Embeddings):
    def __init__(self):
        self.document_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        return [[float(len(text) or 1), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class FakeSparseEmbeddings(SparseEmbeddings):
    def embed_documents(self, texts):
        return [SparseVector(indices=[0], values=[1.0]) for _ in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class QdrantIndexerTests(unittest.TestCase):
    def content_hash(self, content):
        return hashlib.sha256(content.encode()).hexdigest()

    def test_unchanged_content_refreshes_payload_without_embedding(self):
        client = QdrantClient(":memory:")
        client.create_collection("docs", vectors_config={"dense": VectorParams(size=2, distance=Distance.COSINE)})
        point_id = "b8c8059b-ce28-5cff-95f1-fb58a679304f"
        client.upsert(
            "docs",
            [
                PointStruct(
                    id=point_id,
                    vector={"dense": [0.25, 0.75]},
                    payload={
                        "page_content": "unchanged",
                        "metadata": {
                            "title": "old",
                            "_index": {
                                "run_id": "old",
                                "content_hash": self.content_hash("unchanged"),
                                "embedding_fingerprint": "same",
                            },
                        },
                    },
                )
            ],
        )
        embeddings = FakeEmbeddings()
        settings = IndexerSettings(_env_file=None, collection_name="docs", indexing_mode="dense")
        indexer = QdrantIndexer(settings, client=client, dense_embedding=embeddings)
        original_vector = client.retrieve("docs", [point_id], with_vectors=True)[0].vector
        document = Document(
            id=point_id,
            page_content="unchanged",
            metadata={
                "title": "new",
                "_index": {
                    "run_id": "current",
                    "content_hash": self.content_hash("unchanged"),
                    "embedding_fingerprint": "same",
                },
            },
        )

        upserted = indexer.upsert_documents([document])
        stored = client.retrieve("docs", [point_id], with_vectors=True)[0]

        self.assertEqual([], upserted)
        self.assertEqual([], embeddings.document_calls)
        self.assertEqual("new", stored.payload["metadata"]["title"])
        self.assertEqual("current", stored.payload["metadata"]["_index"]["run_id"])
        self.assertEqual(original_vector, stored.vector)

    def test_changed_content_is_embedded_and_upserted(self):
        client = QdrantClient(":memory:")
        client.create_collection("docs", vectors_config={"dense": VectorParams(size=2, distance=Distance.COSINE)})
        point_id = "b8c8059b-ce28-5cff-95f1-fb58a679304f"
        client.upsert(
            "docs",
            [
                PointStruct(
                    id=point_id,
                    vector={"dense": [0.25, 0.75]},
                    payload={
                        "page_content": "old",
                        "metadata": {
                            "_index": {
                                "run_id": "old",
                                "content_hash": self.content_hash("old"),
                                "embedding_fingerprint": "same",
                            }
                        },
                    },
                )
            ],
        )
        embeddings = FakeEmbeddings()
        settings = IndexerSettings(_env_file=None, collection_name="docs", indexing_mode="dense")
        indexer = QdrantIndexer(settings, client=client, dense_embedding=embeddings)
        document = Document(
            id=point_id,
            page_content="changed",
            metadata={
                "_index": {
                    "run_id": "current",
                    "content_hash": self.content_hash("changed"),
                    "embedding_fingerprint": "same",
                }
            },
        )

        upserted = indexer.upsert_documents([document])

        self.assertEqual([point_id], upserted)
        self.assertIn(["changed"], embeddings.document_calls)

    def test_content_hash_not_page_content_decides_unchanged(self):
        client = QdrantClient(":memory:")
        client.create_collection("docs", vectors_config={"dense": VectorParams(size=2, distance=Distance.COSINE)})
        point_id = "b8c8059b-ce28-5cff-95f1-fb58a679304f"
        content_hash = self.content_hash("canonical content")
        client.upsert(
            "docs",
            [
                PointStruct(
                    id=point_id,
                    vector={"dense": [0.25, 0.75]},
                    payload={
                        "page_content": "old stored content",
                        "metadata": {
                            "_index": {
                                "run_id": "old",
                                "content_hash": content_hash,
                                "embedding_fingerprint": "same",
                            }
                        },
                    },
                )
            ],
        )
        embeddings = FakeEmbeddings()
        settings = IndexerSettings(_env_file=None, collection_name="docs", indexing_mode="dense")
        indexer = QdrantIndexer(settings, client=client, dense_embedding=embeddings)
        document = Document(
            id=point_id,
            page_content="new stored content",
            metadata={
                "_index": {
                    "run_id": "current",
                    "content_hash": content_hash,
                    "embedding_fingerprint": "same",
                }
            },
        )

        upserted = indexer.upsert_documents([document])
        stored = client.retrieve("docs", [point_id], with_payload=True, with_vectors=False)[0]

        self.assertEqual([], upserted)
        self.assertEqual([], embeddings.document_calls)
        self.assertEqual("new stored content", stored.payload["page_content"])

    def test_changed_embedding_fingerprint_forces_upsert(self):
        client = QdrantClient(":memory:")
        client.create_collection("docs", vectors_config={"dense": VectorParams(size=2, distance=Distance.COSINE)})
        point_id = "b8c8059b-ce28-5cff-95f1-fb58a679304f"
        client.upsert(
            "docs",
            [
                PointStruct(
                    id=point_id,
                    vector={"dense": [0.25, 0.75]},
                    payload={
                        "page_content": "same content",
                        "metadata": {
                            "_index": {
                                "run_id": "old",
                                "content_hash": self.content_hash("same content"),
                                "embedding_fingerprint": "old-model",
                            }
                        },
                    },
                )
            ],
        )
        embeddings = FakeEmbeddings()
        settings = IndexerSettings(_env_file=None, collection_name="docs", indexing_mode="dense")
        indexer = QdrantIndexer(settings, client=client, dense_embedding=embeddings)
        document = Document(
            id=point_id,
            page_content="same content",
            metadata={
                "_index": {
                    "run_id": "current",
                    "content_hash": self.content_hash("same content"),
                    "embedding_fingerprint": "new-model",
                }
            },
        )

        upserted = indexer.upsert_documents([document])

        self.assertEqual([point_id], upserted)
        self.assertIn(["same content"], embeddings.document_calls)

    def test_dense_upsert_and_prune_remove_stale_and_legacy_points(self):
        client = QdrantClient(":memory:")
        client.create_collection("docs", vectors_config={"dense": VectorParams(size=2, distance=Distance.COSINE)})
        client.upsert(
            "docs",
            [PointStruct(id=1, vector={"dense": [1.0, 1.0]}, payload={"metadata": {}})],
        )
        settings = IndexerSettings(_env_file=None, collection_name="docs", indexing_mode="dense")
        indexer = QdrantIndexer(settings, client=client, dense_embedding=FakeEmbeddings())
        document = Document(
            id="b8c8059b-ce28-5cff-95f1-fb58a679304f",
            page_content="current",
            metadata={"_index": {"run_id": "current"}},
        )

        indexer.upsert_documents([document])
        deleted = indexer.prune_stale("current")
        points, _ = client.scroll("docs", limit=10)

        self.assertEqual(1, deleted)
        self.assertEqual([document.id], [str(point.id) for point in points])

    def test_prune_missing_collection_is_a_noop(self):
        settings = IndexerSettings(_env_file=None, collection_name="missing", indexing_mode="dense")
        indexer = QdrantIndexer(settings, client=QdrantClient(":memory:"), dense_embedding=FakeEmbeddings())
        self.assertEqual(0, indexer.prune_stale("run"))

    def test_hybrid_mode_creates_named_dense_and_sparse_vectors(self):
        client = QdrantClient(":memory:")
        settings = IndexerSettings(_env_file=None, collection_name="hybrid-docs", indexing_mode="hybrid")
        indexer = QdrantIndexer(
            settings,
            client=client,
            dense_embedding=FakeEmbeddings(),
            sparse_embedding=FakeSparseEmbeddings(),
        )
        document = Document(
            id="b8c8059b-ce28-5cff-95f1-fb58a679304f",
            page_content="hybrid content",
            metadata={"_index": {"run_id": "current"}},
        )

        indexer.upsert_documents([document])
        params = client.get_collection("hybrid-docs").config.params

        self.assertIn("dense", params.vectors)
        self.assertIn("sparse", params.sparse_vectors)


if __name__ == "__main__":
    unittest.main()

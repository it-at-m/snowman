from collections.abc import Sequence

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from langchain_qdrant.sparse_embeddings import SparseEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    OverwritePayloadOperation,
    SetPayload,
    SparseVectorParams,
    VectorParams,
)

from src.config.settings import IndexerSettings


class QdrantIndexer:
    """Own Qdrant collection setup, embeddings, batched writes, and pruning."""

    def __init__(
        self,
        config: IndexerSettings,
        *,
        client: QdrantClient | None = None,
        dense_embedding_model: Embeddings | None = None,
        sparse_embedding_model: SparseEmbeddings | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._dense_embedding_model = dense_embedding_model or self._create_dense_embedding_model()
        self._sparse_embedding_model = (
            sparse_embedding_model or self._create_sparse_embedding_model() if config.indexing_mode == "hybrid" else None
        )
        self._vector_store: QdrantVectorStore | None = None

    def _create_dense_embedding_model(self) -> Embeddings:
        print("create dense embedding model")
        kwargs = {
            "model": self.config.openai_embedding_model,
            "timeout": self.config.embedding_timeout,
            "max_retries": self.config.embedding_max_retries,
            "api_key": self.config.openai_api_key,
        }
        if self.config.openai_api_base:
            kwargs["base_url"] = self.config.openai_api_base
        emb_model = OpenAIEmbeddings(**kwargs)
        return emb_model

    def _create_sparse_embedding_model(self) -> SparseEmbeddings:
        emb_model = FastEmbedSparse(
            model_name=self.config.sparse_embedding_model,
            language=self.config.sparse_embedding_language,
            cache_dir=self.config.fastembed_cache_path,
        )
        return emb_model

    def _qdrant_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                port=None,
                timeout=self.config.qdrant_timeout,
            )
        return self._client

    def _qdrant_collection_vector_store(self) -> QdrantVectorStore:
        if self._vector_store is not None:
            return self._vector_store

        client = self._qdrant_client()
        collection = self.config.collection_name
        dense_embedding = self._dense_embedding_model
        hybrid = self.config.indexing_mode == "hybrid"

        if not client.collection_exists(collection):
            vector_size = len(dense_embedding.embed_documents(["dimension probe"])[0])
            sparse_vectors = {self.config.sparse_vector_name: SparseVectorParams()} if hybrid else None
            client.create_collection(
                collection_name=collection,
                vectors_config={self.config.dense_vector_name: VectorParams(size=vector_size, distance=Distance.COSINE)},
                sparse_vectors_config=sparse_vectors,
            )

        self._vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection,
            embedding=dense_embedding,
            retrieval_mode=RetrievalMode.HYBRID if hybrid else RetrievalMode.DENSE,
            vector_name=self.config.dense_vector_name,
            sparse_embedding=self._sparse_embedding_model if hybrid else None,
            sparse_vector_name=self.config.sparse_vector_name,
        )
        return self._vector_store

    def upsert_documents(self, documents: Sequence[Document]) -> list[str]:
        if not documents:
            return []
        ids: list[str] = []
        for document in documents:
            if document.id is None:
                raise ValueError("all indexed chunks require a deterministic point ID")
            ids.append(document.id)

        client = self._qdrant_client()
        collection = self.config.collection_name
        existing_by_id = {}
        if client.collection_exists(collection):
            existing_by_id = {
                str(point.id): point
                for point in client.retrieve(
                    collection_name=collection,
                    ids=ids,
                    with_payload=["metadata._index"],
                    with_vectors=False,
                )
            }

        changed: list[Document] = []
        unchanged: list[Document] = []
        for document in documents:
            existing = existing_by_id.get(str(document.id))
            existing_payload = existing.payload if existing is not None and existing.payload is not None else {}
            existing_index = existing_payload.get("metadata", {}).get("_index", {})
            current_index = document.metadata.get("_index", {})
            current_content_hash = current_index.get("content_hash")
            if (
                current_content_hash is not None
                and existing_index.get("content_hash") == current_content_hash
                and existing_index.get("embedding_fingerprint") == current_index.get("embedding_fingerprint")
            ):
                unchanged.append(document)
            else:
                changed.append(document)

        upserted_ids: list[str] = []
        if changed:
            changed_ids = [document.id for document in changed if document.id is not None]
            upserted_ids = self._qdrant_collection_vector_store().add_documents(
                changed,
                ids=changed_ids,
                batch_size=self.config.indexing_batch_size,
            )

        if unchanged:
            # Qdrant overwrite replaces the entire payload:
            # https://api.qdrant.tech/api-reference/points/overwrite-payload
            # Both LangChain payload fields are required; omitting page_content would remove it.
            # This refreshes metadata (including run_id) while leaving the existing vectors untouched.
            operations = []
            for document in unchanged:
                if document.id is None:
                    raise ValueError("all indexed chunks require a deterministic point ID")
                operations.append(
                    OverwritePayloadOperation(
                        overwrite_payload=SetPayload(
                            payload={"page_content": document.page_content, "metadata": document.metadata},
                            points=[document.id],
                        )
                    )
                )
            client.batch_update_points(collection_name=collection, update_operations=operations, wait=True)

        return upserted_ids

    def prune_stale(self, run_id: str) -> int:
        """Delete points not written by the completed snapshot run."""
        client = self._qdrant_client()
        collection = self.config.collection_name
        if not client.collection_exists(collection):
            return 0

        stale_filter = Filter(must_not=[FieldCondition(key="metadata._index.run_id", match=MatchValue(value=run_id))])
        stale_count = client.count(collection_name=collection, count_filter=stale_filter, exact=True).count
        if stale_count:
            client.delete(collection_name=collection, points_selector=stale_filter, wait=True)
        return stale_count

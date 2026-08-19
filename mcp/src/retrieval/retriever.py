import warnings

from cohere import ClientV2
from cohere.v2.types import V2RerankResponse
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, Fusion, FusionQuery, VectorParams

from src.config.settings import RetrievalSettings
from src.utils.logtools import getLogger

logger = getLogger()


class Retriever:
    """Small retrieval service for hybrid search in Qdrant.

    The class owns the expensive clients/models and creates them lazily. That keeps
    MCP server startup fast and makes configuration or network problems appear only
    when retrieval is actually used.
    """

    def __init__(self, config: RetrievalSettings) -> None:
        self.config = config
        self._qdrant_client: QdrantClient | None = None
        self._embedding_model: Embeddings | None = None
        self._sparse_embedding_model: FastEmbedSparse | None = None
        self._retrievers: dict[str, VectorStoreRetriever] = {}
        self.rerank_client: ClientV2 | None = self._build_reranker() if self.config.rerank_enabled else None

        for collection in self.config.collections_list:
            logger.info(f"Initializing retriever for collection {collection}")
            self._build_retriever(collection)

    @staticmethod
    def interleave_document_lists(doc_lists: list[list[Document]], n_final=5) -> list[Document]:
        """Interleave multiple ranked document lists while preserving per-list order.

        Example:
            [[a1, a2], [b1, b2, b3]] -> [a1, b1, a2, b2, b3]
        """
        merged: list[Document] = []
        max_len = max((len(docs) for docs in doc_lists), default=0)

        for i in range(max_len):
            for docs in doc_lists:
                if i < len(docs) and isinstance(docs[i], Document):
                    merged.append(docs[i])

        return merged[:n_final]

    def _build_documents_by_collection(self, documents: list[Document]) -> dict[str, list[Document]]:
        """Group a flat list of Documents by their 'collection' metadata."""
        documents_by_collection: dict[str, list[Document]] = {}
        for doc in documents:
            key = doc.metadata.get("collection", "unknown")
            if key not in documents_by_collection:
                documents_by_collection[key] = []
            documents_by_collection[key].append(doc)
        return documents_by_collection

    def _build_qdrant_client(self) -> QdrantClient:
        """Create the shared Qdrant client.

        We use the read-only API key because this MCP server only retrieves data.
        Indexing and collection writes should stay in the indexer service.
        """
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_readonly_api_key,
                port=None,
                timeout=self.config.qdrant_timeout,
            )
        return self._qdrant_client

    def _build_embedding_model(self) -> Embeddings:
        """Create the dense embedding model used for semantic search."""
        if self._embedding_model is None:
            kwargs = {
                "model": self.config.openai_embedding_model,
                "timeout": self.config.embedding_timeout,
                "max_retries": self.config.embedding_max_retries,
                "api_key": self.config.openai_api_key,
            }
            if self.config.openai_api_base:
                kwargs["base_url"] = self.config.openai_api_base

            self._embedding_model = OpenAIEmbeddings(**kwargs)
        return self._embedding_model

    def _build_sparse_embedding_model(self) -> FastEmbedSparse:
        """Create the sparse BM25 model used for keyword-style matching."""
        if self._sparse_embedding_model is None:
            self._sparse_embedding_model = FastEmbedSparse(
                model_name=self.config.sparse_embedding_model,
                language=self.config.sparse_embedding_language,
                cache_dir=self.config.fastembed_cache_path,
            )
        return self._sparse_embedding_model

    def _build_vectorstore(self, collection: str | None = None) -> QdrantVectorStore:
        """Create a LangChain vector store for one Qdrant collection."""
        collection_name = collection or self.config.collections_list[0]
        client = self._build_qdrant_client()

        if not client.collection_exists(collection_name):
            raise ValueError(f"Qdrant collection '{collection_name}' does not exist")

        params = client.get_collection(collection_name).config.params
        # Unnamed legacy config -> VectorParams; named config -> dict[str, VectorParams]
        unnamed = isinstance(params.vectors, VectorParams)
        has_sparse = bool(params.sparse_vectors) and (
            self.config.sparse_vector_name in (params.sparse_vectors or {})
        )

        if unnamed or not has_sparse:
            return QdrantVectorStore(
                client=client,
                collection_name=collection_name,
                embedding=self._build_embedding_model(),
                retrieval_mode=RetrievalMode.DENSE,
                vector_name="" if unnamed else self.config.dense_vector_name,
            )

        return QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name=self.config.dense_vector_name,
            embedding=self._build_embedding_model(),
            sparse_vector_name=self.config.sparse_vector_name,
            sparse_embedding=self._build_sparse_embedding_model(),
        )

    def _build_retriever(self, collection: str | None = None, filter: Filter | None = None) -> VectorStoreRetriever:
        """Create a threshold retriever for one collection."""
        collection_name = collection or self.config.collections_list[0]

        if collection_name not in self._retrievers:
            fusion = Fusion.DBSF if self.config.retrieval_fusion == "DBSF" else Fusion.RRF

            # LangChain can warn because Qdrant hybrid scores are not always in [0, 1].
            # This warning is expected for hybrid search, so keep the suppression local.
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, message=".*Relevance scores.*")
                self._retrievers[collection_name] = self._build_vectorstore(collection_name).as_retriever(
                    search_type="similarity_score_threshold",
                    search_kwargs={
                        "score_threshold": self.config.retrieval_score_threshold,
                        "k": self.config.retrieval_n_docs,
                        "hybrid_fusion": FusionQuery(fusion=fusion),
                        "filter": filter
                    },
                )
        return self._retrievers[collection_name]

    def _build_reranker(self) -> ClientV2:
        """Create a Cohere reranker client for re-ranking retrieved documents.
        The client is cheap and stateless; we keep a single instance on the
        class to avoid per-call construction overhead.
        """
        return ClientV2(api_key=self.config.openai_api_key, base_url=self.config.openai_api_base)

    def _rerank_documents(self, query: str, documents: dict[str, list[Document]]) -> dict[str, list[Document]]:
        """Rerank the retrieved documents using the configured reranker model.

        Steps:
        1. Interleave per-collection lists to preserve each list's internal order
           while mixing sources, then cap to an upper bound for reranking.
        2. Call the external reranker with only page_content (no metadata) to get
           semantic relevance scores for the specific query.
        3. Write scores back onto the corresponding Document.metadata.
        4. Sort by those scores desc and keep only the configured final top-k.
        5. Re-group back into a collection->docs mapping for the MCP response.
        """
        if not self.rerank_client:
            raise ValueError("Reranker client is not initialized. Ensure reranking is enabled in the configuration.")

        # Mix documents from each collection while preserving per-collection order,
        # and cap the list length sent to the reranker to avoid excessive payloads.
        docs = Retriever.interleave_document_lists(
            list(documents.values()),
            n_final=self.config.retrieval_n_docs * len(list(documents.keys())),
        )
        rerank_response: V2RerankResponse = self.rerank_client.rerank(
            model=self.config.rerank_model,
            query=query,
            documents=[doc.page_content for doc in docs],
        )
        # The API returns indices back into the provided documents array; attach
        # scores onto the matching Document so we can sort in-place below.
        for result in rerank_response.results:
            docs[result.index].metadata["relevance_score"] = result.relevance_score

        # Higher score means more relevant; keep only the final top-N requested.
        docs.sort(key=lambda d: d.metadata.get("relevance_score", 0), reverse=True)
        final_docs = docs[: self.config.retrieval_final_n_docs]
        # Shape the response back into the collection->docs mapping expected by callers.
        return self._build_documents_by_collection(final_docs)

    def retrieve_documents(self, query: str, filter: Filter | None) -> dict[str, list[Document]]:
        """Retrieve matching documents from all configured collections."""
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("query must not be empty")

        documents_by_collection: dict[str, list[Document]] = {}
        for collection in self.config.collections_list:
            retriever = self._build_retriever(collection)
            documents_by_collection[collection] = retriever.invoke(cleaned_query, filter=filter)

        if not self.config.rerank_enabled:
            document_list = Retriever.interleave_document_lists(
                list(documents_by_collection.values()), n_final=self.config.retrieval_final_n_docs
            )
            return self._build_documents_by_collection(document_list)
        return self._rerank_documents(cleaned_query, documents_by_collection)

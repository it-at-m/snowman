import hashlib
import json
import logging
import uuid
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.settings import IndexerSettings
from src.indexer.qdrant_indexer import QdrantIndexer
from src.indexer.source import DocumentSource

logger = logging.getLogger(__name__)
POINT_ID_NAMESPACE = uuid.UUID("65b31099-4e3e-4b49-9cf7-638ef0bbd8d4")


class InvalidSourceDocumentError(ValueError):
    """Raised when an adapter violates the canonical document contract."""


class EmptySnapshotError(ValueError):
    """Raised when an empty snapshot could otherwise erase an index."""


@dataclass(frozen=True)
class IndexingResult:
    run_id: str
    source_documents: int
    chunks_upserted: int
    stale_points_deleted: int


class IndexingPipeline:
    """Source-neutral orchestration from canonical documents to Qdrant."""

    def __init__(self, config: IndexerSettings, indexer: QdrantIndexer | None = None) -> None:
        self.config = config
        self.indexer = indexer or QdrantIndexer(config)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size= self.indexer._dense_embedding_model.embedding_ctx_length - self.indexer._dense_embedding_model.embedding_ctx_length * 0.1 if self.indexer._dense_embedding_model.embedding_ctx_length else config.document_chunk_size, # type: ignore
            chunk_overlap=config.document_chunk_overlap if config.document_chunk_overlap < self.indexer._dense_embedding_model.embedding_ctx_length else 0, # type: ignore
        )
        print(f"dense embedding model context length: {self.indexer._dense_embedding_model.embedding_ctx_length}") # type: ignore
        embedding_config = {
            "indexing_mode": config.indexing_mode,
            "openai_api_base": config.openai_api_base,
            "openai_embedding_model": config.openai_embedding_model,
            "sparse_embedding_language": config.sparse_embedding_language if config.indexing_mode == "hybrid" else None,
            "sparse_embedding_model": config.sparse_embedding_model if config.indexing_mode == "hybrid" else None,
        }
        serialized_config = json.dumps(embedding_config, sort_keys=True, separators=(",", ":"))
        self._embedding_fingerprint = hashlib.sha256(serialized_config.encode()).hexdigest()

    def _chunks_for(self, document: Document, run_id: str) -> list[Document]:
        if document.id is None or not document.id.strip():
            raise InvalidSourceDocumentError("every source Document requires a stable, non-empty id")
        if not document.page_content.strip():
            raise InvalidSourceDocumentError(f"source Document {document.id!r} has empty page_content")
        if "_index" in document.metadata:
            raise InvalidSourceDocumentError("source metadata key _index is reserved by the pipeline")
        try:
            json.dumps(document.metadata)
        except (TypeError, ValueError) as error:
            raise InvalidSourceDocumentError(f"source Document {document.id!r} metadata must be JSON-compatible") from error

        texts = self._splitter.split_text(document.page_content)
        chunks: list[Document] = []
        for chunk_index, text in enumerate(texts):
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            point_id = str(
                uuid.uuid5(
                    POINT_ID_NAMESPACE,
                    f"{self.config.collection_name}\0{document.id}\0{chunk_index}",
                )
            )
            metadata = dict(document.metadata)
            metadata["collection"] = self.config.collection_name
            metadata["_index"] = {
                "run_id": run_id,
                "source_document_id": document.id,
                "chunk_index": chunk_index,
                "chunk_count": len(texts),
                "content_hash": content_hash,
                "embedding_fingerprint": self._embedding_fingerprint,
            }
            chunks.append(Document(id=point_id, page_content=text, metadata=metadata))
        return chunks

    def run(self, source: DocumentSource) -> IndexingResult:
        run_id = str(uuid.uuid4())
        seen_document_ids: set[str] = set()
        batch: list[Document] = []
        source_count = 0
        chunk_count = 0

        for document in source.load_documents():
            if not isinstance(document, Document):
                raise InvalidSourceDocumentError("DocumentSource must yield LangChain Document instances")
            if document.id in seen_document_ids:
                raise InvalidSourceDocumentError(f"duplicate source Document id: {document.id}")
            if document.id is not None:
                seen_document_ids.add(document.id)

            source_count += 1
            for chunk in self._chunks_for(document, run_id):
                batch.append(chunk)
                if len(batch) >= self.config.indexing_batch_size:
                    chunk_count += len(self.indexer.upsert_documents(batch))
                    batch.clear()

        if source_count == 0 and not self.config.allow_empty_snapshot:
            raise EmptySnapshotError(
                "source returned no documents; existing points were preserved. "
                "Set ALLOW_EMPTY_SNAPSHOT=true to make an empty snapshot authoritative."
            )
        if batch:
            chunk_count += len(self.indexer.upsert_documents(batch))

        deleted_count = self.indexer.prune_stale(run_id)
        result = IndexingResult(
            run_id=run_id,
            source_documents=source_count,
            chunks_upserted=chunk_count,
            stale_points_deleted=deleted_count,
        )
        logger.info(
            "Indexing snapshot completed",
            extra={
                "run_id": result.run_id,
                "source_documents": result.source_documents,
                "chunks_upserted": result.chunks_upserted,
                "stale_points_deleted": result.stale_points_deleted,
            },
        )
        return result

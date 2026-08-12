import unittest

from langchain_core.documents import Document
from src.config.settings import IndexerSettings
from src.indexer.pipeline import EmptySnapshotError, IndexingPipeline, InvalidSourceDocumentError


class StaticSource:
    def __init__(self, documents):
        self.documents = documents

    def load_documents(self):
        return iter(self.documents)


class RecordingIndexer:
    def __init__(self, *, fail=False):
        self.batches = []
        self.pruned_run_id = None
        self.fail = fail

    def upsert_documents(self, documents):
        if self.fail:
            raise RuntimeError("upload failed")
        self.batches.append(list(documents))
        return [document.id for document in documents]

    def prune_stale(self, run_id):
        self.pruned_run_id = run_id
        return 3


class IndexingPipelineTests(unittest.TestCase):
    def settings(self, **kwargs):
        values = {
            "collection_name": "docs",
            "document_chunk_size": 10,
            "document_chunk_overlap": 2,
            "indexing_batch_size": 2,
        }
        values.update(kwargs)
        return IndexerSettings(_env_file=None, **values)

    def test_chunks_are_deterministic_batched_and_enriched(self):
        recorder = RecordingIndexer()
        pipeline = IndexingPipeline(self.settings(), recorder)
        source = StaticSource([Document(id="one", page_content="alpha beta gamma", metadata={"title": "A"})])

        first = pipeline.run(source)
        first_chunks = [chunk for batch in recorder.batches for chunk in batch]
        first_ids = [chunk.id for chunk in first_chunks]

        second_recorder = RecordingIndexer()
        IndexingPipeline(self.settings(), second_recorder).run(source)
        second_ids = [chunk.id for batch in second_recorder.batches for chunk in batch]

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(1, first.source_documents)
        self.assertEqual(3, first.stale_points_deleted)
        self.assertTrue(all(len(batch) <= 2 for batch in recorder.batches))
        self.assertEqual("docs", first_chunks[0].metadata["collection"])
        self.assertEqual("one", first_chunks[0].metadata["_index"]["source_document_id"])
        self.assertEqual(64, len(first_chunks[0].metadata["_index"]["content_hash"]))
        self.assertEqual(64, len(first_chunks[0].metadata["_index"]["embedding_fingerprint"]))
        self.assertEqual("A", first_chunks[0].metadata["title"])
        self.assertEqual(first.run_id, recorder.pruned_run_id)

    def test_empty_snapshot_preserves_existing_points_by_default(self):
        recorder = RecordingIndexer()
        with self.assertRaises(EmptySnapshotError):
            IndexingPipeline(self.settings(), recorder).run(StaticSource([]))
        self.assertIsNone(recorder.pruned_run_id)

    def test_empty_snapshot_can_be_authoritative(self):
        recorder = RecordingIndexer()
        result = IndexingPipeline(self.settings(allow_empty_snapshot=True), recorder).run(StaticSource([]))
        self.assertEqual(0, result.chunks_upserted)
        self.assertIsNotNone(recorder.pruned_run_id)

    def test_upload_failure_never_prunes(self):
        recorder = RecordingIndexer(fail=True)
        source = StaticSource([Document(id="one", page_content="alpha beta gamma")])
        with self.assertRaises(RuntimeError):
            IndexingPipeline(self.settings(indexing_batch_size=1), recorder).run(source)
        self.assertIsNone(recorder.pruned_run_id)

    def test_rejects_invalid_documents(self):
        invalid = [
            Document(page_content="content"),
            Document(id="empty", page_content=" "),
            Document(id="reserved", page_content="content", metadata={"_index": {}}),
            Document(id="metadata", page_content="content", metadata={"bad": object()}),
        ]
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(InvalidSourceDocumentError):
                    IndexingPipeline(self.settings(), RecordingIndexer()).run(StaticSource([document]))

    def test_rejects_duplicate_source_ids(self):
        documents = [
            Document(id="same", page_content="first"),
            Document(id="same", page_content="second"),
        ]
        with self.assertRaises(InvalidSourceDocumentError):
            IndexingPipeline(self.settings(), RecordingIndexer()).run(StaticSource(documents))


if __name__ == "__main__":
    unittest.main()

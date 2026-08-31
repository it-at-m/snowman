import unittest

from qdrant_client import models
from src.config.settings import RetrievalFilterCondition, RetrievalToolSettings
from src.retrieval.filters import build_retrieval_filter


class RetrievalFilterTests(unittest.TestCase):
    def test_combines_base_and_tool_conditions_with_must_semantics(self) -> None:
        base_conditions = [
            RetrievalFilterCondition(field="metadata.source_id", values=["snow-kb"]),
            RetrievalFilterCondition(field="metadata.tenant", values=["munich", "shared"]),
        ]
        tool = RetrievalToolSettings(
            name="search_eakte",
            title="Search E-Akte",
            description="Search E-Akte articles.",
            conditions=[RetrievalFilterCondition(field="payload.custom_topic", values=["eakte"])],
        )

        qdrant_filter = build_retrieval_filter(base_conditions, tool)

        self.assertEqual(3, len(qdrant_filter.must))
        self.assertEqual(
            ["metadata.source_id", "metadata.tenant", "payload.custom_topic"],
            [condition.key for condition in qdrant_filter.must],
        )
        self.assertIsInstance(qdrant_filter.must[0].match, models.MatchValue)
        self.assertEqual("snow-kb", qdrant_filter.must[0].match.value)
        self.assertIsInstance(qdrant_filter.must[1].match, models.MatchAny)
        self.assertEqual(["munich", "shared"], qdrant_filter.must[1].match.any)

    def test_general_tool_still_receives_every_base_condition(self) -> None:
        base_conditions = [
            RetrievalFilterCondition(field="metadata.source_id", values=["snow-kb"]),
            RetrievalFilterCondition(field="metadata.visibility", values=["public"]),
        ]
        tool = RetrievalToolSettings(
            name="search_snow",
            title="Search SNOW",
            description="Search all articles.",
        )

        qdrant_filter = build_retrieval_filter(base_conditions, tool)

        self.assertEqual(
            ["metadata.source_id", "metadata.visibility"],
            [condition.key for condition in qdrant_filter.must],
        )


if __name__ == "__main__":
    unittest.main()

"""Build server-controlled Qdrant filters for configured retrieval tools."""

from qdrant_client import models

from src.config.settings import RetrievalFilterCondition, RetrievalToolSettings


def _build_field_condition(
    condition: RetrievalFilterCondition,
) -> models.FieldCondition:
    """Convert one configured field and its allowed values to Qdrant models."""
    if len(condition.values) == 1:
        match = models.MatchValue(value=condition.values[0])
    else:
        # MatchAny gives values within one condition OR semantics.
        match = models.MatchAny(any=condition.values)

    return models.FieldCondition(key=condition.field, match=match)


def build_retrieval_filter(
    base_conditions: list[RetrievalFilterCondition],
    tool: RetrievalToolSettings,
) -> models.Filter:
    """Combine mandatory base scope and optional tool scope with AND semantics."""
    conditions = [*base_conditions, *tool.conditions]
    return models.Filter(must=[_build_field_condition(condition) for condition in conditions])

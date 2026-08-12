from collections.abc import Iterable
from typing import Protocol

from langchain_core.documents import Document


class DocumentSource(Protocol):
    """The only interface a source-specific adapter must implement."""

    def load_documents(self) -> Iterable[Document]:
        """Yield a complete authoritative snapshot of canonical documents."""
        ...

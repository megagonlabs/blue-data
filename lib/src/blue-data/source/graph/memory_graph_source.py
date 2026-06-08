from __future__ import annotations

from source.graph.graph_source import GraphSource


class MemoryGraphSource(GraphSource):
    """In-memory graph storage backend for local/dev/test use."""

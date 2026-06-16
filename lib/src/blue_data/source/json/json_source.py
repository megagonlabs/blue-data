from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from blue_data.source.source import DataSource


class JSONSource(DataSource, ABC):
    """Abstract JSON storage interface."""

    def __init__(self, name: str = "", properties: dict | None = None):
        super().__init__(name, properties=properties)

    @abstractmethod
    def get(self, path: str | None = None) -> Any:
        pass

    @abstractmethod
    def set(self, path: str | None, value: Any) -> None:
        pass

    @abstractmethod
    def delete(self, path: str | None = None) -> None:
        pass

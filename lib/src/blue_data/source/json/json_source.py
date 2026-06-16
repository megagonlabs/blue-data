from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JSONSource(ABC):
    """Abstract JSON storage interface."""

    @abstractmethod
    def get(self, path: str | None = None) -> Any:
        pass

    @abstractmethod
    def set(self, path: str | None, value: Any) -> None:
        pass

    @abstractmethod
    def delete(self, path: str | None = None) -> None:
        pass
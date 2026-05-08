from __future__ import annotations

from abc import ABC, abstractmethod


class Operator(ABC):
    """Base abstraction for executable data operators."""

    @abstractmethod
    def execute(self, inputs):
        pass
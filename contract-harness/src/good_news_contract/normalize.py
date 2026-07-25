from __future__ import annotations

from copy import deepcopy
from typing import Any


class Normalizer:
    """Normalizes only explicitly documented volatile fields."""

    def __init__(self, volatile_fields: frozenset[str]) -> None:
        self._volatile_fields = volatile_fields

    def value(self, value: Any) -> Any:
        normalized = deepcopy(value)
        return self._walk(normalized)

    def _walk(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "<volatile>" if key in self._volatile_fields else self._walk(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [self._walk(child) for child in value]
        if isinstance(value, tuple):
            return tuple(self._walk(child) for child in value)
        return value

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Step:
    method: str
    path: str
    json_body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    name: str
    route_group: str
    mode: str
    steps: tuple[Step, ...]
    tables: tuple[str, ...] = ()
    target: str = "default"


@dataclass(frozen=True)
class HttpObservation:
    status: int
    error_class: str | None
    body: Any
    location: str | None


@dataclass(frozen=True)
class ScenarioObservation:
    http: tuple[HttpObservation, ...]
    tables: dict[str, list[dict[str, Any]]]
    side_effects: list[dict[str, Any]]


@dataclass(frozen=True)
class Difference:
    path: str
    python_value: Any
    java_value: Any

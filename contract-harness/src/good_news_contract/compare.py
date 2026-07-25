from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .model import Difference, ScenarioObservation
from .normalize import Normalizer


class ContractMismatch(AssertionError):
    def __init__(self, scenario: str, differences: list[Difference]) -> None:
        self.scenario = scenario
        self.differences = differences
        rendered = "\n".join(
            f"  {difference.path}: python={difference.python_value!r}, java={difference.java_value!r}"
            for difference in differences
        )
        super().__init__(f"{scenario} contract mismatch:\n{rendered}")


def compare_observations(
    scenario: str,
    python: ScenarioObservation,
    java: ScenarioObservation,
    normalizer: Normalizer,
) -> None:
    differences: list[Difference] = []
    _diff(
        normalizer.value(asdict(python)),
        normalizer.value(asdict(java)),
        "$",
        differences,
    )
    if differences:
        raise ContractMismatch(scenario, differences)


def _diff(python: Any, java: Any, path: str, differences: list[Difference]) -> None:
    if type(python) is not type(java):
        differences.append(Difference(path, python, java))
        return
    if isinstance(python, dict):
        keys = sorted(set(python) | set(java))
        for key in keys:
            child_path = f"{path}.{key}"
            if key not in python:
                differences.append(Difference(child_path, "<missing>", java[key]))
            elif key not in java:
                differences.append(Difference(child_path, python[key], "<missing>"))
            else:
                _diff(python[key], java[key], child_path, differences)
        return
    if isinstance(python, (list, tuple)):
        if len(python) != len(java):
            differences.append(Difference(f"{path}.length", len(python), len(java)))
        for index, (python_item, java_item) in enumerate(zip(python, java, strict=False)):
            _diff(python_item, java_item, f"{path}[{index}]", differences)
        return
    if python != java:
        differences.append(Difference(path, python, java))

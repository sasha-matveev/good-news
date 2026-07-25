from __future__ import annotations

import json
from pathlib import Path

from .model import Scenario, Step


def load_scenarios(path: Path) -> tuple[Scenario, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios = []
    for item in payload["scenarios"]:
        steps = tuple(
            Step(
                method=step["method"].upper(),
                path=step["path"],
                json_body=step.get("json"),
                headers=step.get("headers", {}),
            )
            for step in item["steps"]
        )
        scenarios.append(
            Scenario(
                name=item["name"],
                route_group=item["route_group"],
                mode=item["mode"],
                steps=steps,
                tables=tuple(item.get("tables", ())),
                target=item.get("target", "default"),
            )
        )
    return tuple(scenarios)


def load_route_groups(path: Path) -> tuple[str, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(payload["active_route_groups"])

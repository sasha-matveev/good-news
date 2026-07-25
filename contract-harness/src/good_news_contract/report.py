from __future__ import annotations

from collections import defaultdict

from .model import Scenario


def parity_report(
    active_route_groups: tuple[str, ...],
    scenarios: tuple[Scenario, ...],
    results: dict[str, str],
) -> str:
    by_group: dict[str, list[Scenario]] = defaultdict(list)
    for scenario in scenarios:
        by_group[scenario.route_group].append(scenario)

    lines = [
        "# Backend parity report",
        "",
        "| Route group | Differential scenarios | Read-only scenarios | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    go = True
    for group in active_route_groups:
        group_scenarios = by_group[group]
        differential = sum(item.mode in {"differential", "both"} for item in group_scenarios)
        read_only = sum(item.mode in {"read-only", "both"} for item in group_scenarios)
        statuses = [results.get(item.name, "not-run") for item in group_scenarios]
        if not group_scenarios:
            result = "missing"
        elif "failed" in statuses:
            result = "failed"
        elif all(status == "passed" for status in statuses):
            result = "passed"
        else:
            result = "not-run"
        go = go and differential > 0 and result == "passed"
        lines.append(f"| {group} | {differential} | {read_only} | {result} |")
    lines.extend(
        [
            "",
            "## Scenario results",
            "",
            "| Route group | Scenario | Mode | Result |",
            "| --- | --- | --- | --- |",
        ]
    )
    for scenario in scenarios:
        lines.append(
            f"| {scenario.route_group} | {scenario.name} | {scenario.mode} | "
            f"{results.get(scenario.name, 'not-run')} |"
        )
    lines.extend(["", f"**Go/no-go:** {'GO' if go else 'NO-GO'}", ""])
    return "\n".join(lines)

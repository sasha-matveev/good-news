from __future__ import annotations

from pathlib import Path

from good_news_contract.manifest import load_route_groups, load_scenarios
from good_news_contract.report import parity_report
from good_news_contract.normalize import Normalizer
from good_news_contract.runner import Harness, HarnessConfig

ROOT = Path(__file__).resolve().parents[1]


def test_every_active_route_group_has_a_differential_scenario() -> None:
    groups = load_route_groups(ROOT / "scenarios.json")
    scenarios = load_scenarios(ROOT / "scenarios.json")

    covered = {
        scenario.route_group
        for scenario in scenarios
        if scenario.mode in {"differential", "both"}
    }

    assert covered == set(groups)


def test_reaction_slice_covers_success_failure_idempotency_and_read_after_write() -> None:
    scenarios = load_scenarios(ROOT / "scenarios.json")
    reaction_names = {
        scenario.name
        for scenario in scenarios
        if scenario.route_group in {"feedback", "want-to-read"}
    }

    assert {
        "feedback-success-update-and-read-after-write",
        "feedback-idempotent",
        "feedback-not-found",
        "feedback-validation",
        "feedback-public-redirect",
        "want-to-read-reaction-and-read-after-write",
    } <= reaction_names


def test_report_is_no_go_until_every_scenario_passes() -> None:
    scenarios = load_scenarios(ROOT / "scenarios.json")
    groups = load_route_groups(ROOT / "scenarios.json")

    report = parity_report(groups, scenarios, {})

    assert "**Go/no-go:** NO-GO" in report
    assert "| feedback |" in report


def test_read_only_mode_rejects_mutating_scenario() -> None:
    scenario = next(
        item
        for item in load_scenarios(ROOT / "scenarios.json")
        if item.name == "feedback-idempotent"
    )
    harness = Harness(
        HarnessConfig("python", "java", "db", "db", "effects", ROOT / "fixtures" / "seed.sql"),
        Normalizer(frozenset()),
    )

    scenario = type(scenario)(
        scenario.name,
        scenario.route_group,
        "both",
        scenario.steps,
        scenario.tables,
        scenario.target,
    )

    try:
        harness.run_read_only(scenario)
    except ValueError as exc:
        assert "forbids mutating methods" in str(exc)
    else:
        raise AssertionError("read-only mode accepted a PUT scenario")

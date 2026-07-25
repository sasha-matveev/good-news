from __future__ import annotations

import argparse
import os
from pathlib import Path

from .manifest import load_route_groups, load_scenarios
from .normalize import Normalizer
from .report import parity_report
from .runner import Harness, HarnessConfig

ROOT = Path(
    os.getenv("GOOD_NEWS_CONTRACT_ROOT", Path.cwd() / "contract-harness")
).resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("differential", "read-only"), default="differential")
    parser.add_argument("--scenario")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "parity.md")
    args = parser.parse_args()

    manifest_path = ROOT / "scenarios.json"
    scenarios = load_scenarios(manifest_path)
    if args.scenario:
        scenarios = tuple(item for item in scenarios if item.name == args.scenario)
        if not scenarios:
            parser.error(f"unknown scenario: {args.scenario}")

    config = HarnessConfig(
        python_url=_required("GOOD_NEWS_CONTRACT_PYTHON_URL"),
        java_url=_required("GOOD_NEWS_CONTRACT_JAVA_URL"),
        python_database_url=_required("GOOD_NEWS_CONTRACT_PYTHON_DATABASE_URL"),
        java_database_url=os.getenv(
            "GOOD_NEWS_CONTRACT_JAVA_DATABASE_URL",
            _required("GOOD_NEWS_CONTRACT_PYTHON_DATABASE_URL"),
        ),
        side_effects_url=_required("GOOD_NEWS_CONTRACT_SIDE_EFFECTS_URL"),
        seed_file=ROOT / "fixtures" / "seed.sql",
        python_auth_url=os.getenv("GOOD_NEWS_CONTRACT_PYTHON_AUTH_URL"),
        java_auth_url=os.getenv("GOOD_NEWS_CONTRACT_JAVA_AUTH_URL"),
    )
    harness = Harness(config, Normalizer(frozenset({"id", "created_at", "updated_at", "sent_at", "correlation_id"})))
    harness.wait_until_ready()
    results = {}
    for scenario in scenarios:
        applies = (
            scenario.mode in {"differential", "both"}
            if args.mode == "differential"
            else scenario.mode in {"read-only", "both"}
        )
        if not applies:
            continue
        try:
            if args.mode == "differential":
                harness.run_differential(scenario)
            else:
                harness.run_read_only(scenario)
            results[scenario.name] = "passed"
            print(f"PASS {scenario.route_group}/{scenario.name}")
        except Exception as exc:
            results[scenario.name] = "failed"
            print(f"FAIL {scenario.route_group}/{scenario.name}: {exc}")

    report = parity_report(load_route_groups(manifest_path), scenarios, results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    if "failed" in results.values():
        raise SystemExit(1)


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable {name}")
    return value


if __name__ == "__main__":
    main()

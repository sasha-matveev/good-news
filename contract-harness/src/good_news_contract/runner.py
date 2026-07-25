from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import httpx

from .compare import compare_observations
from .database import Database
from .model import HttpObservation, Scenario, ScenarioObservation
from .normalize import Normalizer


@dataclass(frozen=True)
class HarnessConfig:
    python_url: str
    java_url: str
    python_database_url: str
    java_database_url: str
    side_effects_url: str
    seed_file: Path
    python_auth_url: str | None = None
    java_auth_url: str | None = None


class Harness:
    def __init__(self, config: HarnessConfig, normalizer: Normalizer) -> None:
        self._config = config
        self._normalizer = normalizer

    def wait_until_ready(self, timeout_seconds: float = 90) -> None:
        urls = [
            self._config.python_url,
            self._config.java_url,
            self._config.python_auth_url,
            self._config.java_auth_url,
        ]
        deadline = monotonic() + timeout_seconds
        pending = {url for url in urls if url}
        while pending and monotonic() < deadline:
            for url in tuple(pending):
                try:
                    response = httpx.get(f"{url}/api/health", timeout=2)
                    if response.status_code == 200:
                        pending.remove(url)
                except httpx.HTTPError:
                    pass
            if pending:
                sleep(1)
        if pending:
            raise TimeoutError(f"Backends did not become ready: {sorted(pending)}")

    def run_differential(self, scenario: Scenario) -> None:
        if scenario.mode not in {"differential", "both"}:
            return
        python_database = Database(self._config.python_database_url)
        java_database = Database(self._config.java_database_url)
        python_database.seed(self._config.seed_file)
        java_database.seed(self._config.seed_file)
        python_url, java_url = self._urls(scenario)
        python = self._observe(
            "python", python_url, python_database, scenario
        )
        java = self._observe("java", java_url, java_database, scenario)
        compare_observations(scenario.name, python, java, self._normalizer)

    def run_read_only(self, scenario: Scenario) -> None:
        if scenario.mode not in {"read-only", "both"}:
            return
        if any(step.method not in {"GET", "HEAD", "OPTIONS"} for step in scenario.steps):
            raise ValueError(f"{scenario.name}: read-only mode forbids mutating methods")
        shared_database = Database(self._config.python_database_url)
        shared_database.seed(self._config.seed_file)
        python_url, java_url = self._urls(scenario)
        python = self._observe(
            "python", python_url, shared_database, scenario
        )
        java = self._observe("java", java_url, shared_database, scenario)
        compare_observations(scenario.name, python, java, self._normalizer)

    def _observe(
        self,
        backend: str,
        base_url: str,
        database: Database,
        scenario: Scenario,
    ) -> ScenarioObservation:
        self._clear_side_effects()
        observations = []
        with httpx.Client(base_url=base_url, follow_redirects=False, timeout=20) as client:
            for step in scenario.steps:
                response = client.request(
                    step.method,
                    step.path,
                    json=step.json_body,
                    headers=step.headers,
                )
                observations.append(self._http_observation(response))
        return ScenarioObservation(
            http=tuple(observations),
            tables=database.snapshot(scenario.tables),
            side_effects=self._side_effects(),
        )

    @staticmethod
    def _http_observation(response: httpx.Response) -> HttpObservation:
        content_type = response.headers.get("content-type", "")
        body: Any = response.json() if "json" in content_type else response.text
        error_class = None
        if response.status_code >= 400:
            if isinstance(body, dict) and "detail" in body:
                detail = body["detail"]
                error_class = detail if isinstance(detail, str) else "validation"
            else:
                error_class = response.reason_phrase
        return HttpObservation(
            status=response.status_code,
            error_class=error_class,
            body=body,
            location=response.headers.get("location"),
        )

    def _clear_side_effects(self) -> None:
        httpx.delete(f"{self._config.side_effects_url}/events", timeout=10).raise_for_status()

    def _side_effects(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self._config.side_effects_url}/events", timeout=10)
        response.raise_for_status()
        return response.json()["events"]

    def _urls(self, scenario: Scenario) -> tuple[str, str]:
        if scenario.target != "auth":
            return self._config.python_url, self._config.java_url
        if not self._config.python_auth_url or not self._config.java_auth_url:
            raise ValueError(f"{scenario.name}: auth target URLs are not configured")
        return self._config.python_auth_url, self._config.java_auth_url

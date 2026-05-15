from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.migration_runner import ALEMBIC_LOCK_ID, default_migration_command, postgres_driver_url, run_migrations_with_lock


def test_postgres_driver_url_normalizes_sqlalchemy_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_PASSWORD", "phase3-secret")

    settings = Settings.from_env()

    assert postgres_driver_url(settings) == "postgresql://good_news:phase3-secret@localhost:5432/good_news"


def test_run_migrations_with_lock_serializes_alembic_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOD_NEWS_POSTGRES_PASSWORD", "phase3-secret")
    settings = Settings.from_env()
    events: list[object] = []

    class FakeCursor:
        def execute(self, sql: str, params: tuple[int]) -> None:
            events.append((sql, params))

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            events.append("closed")

    def fake_connect(url: str) -> FakeConnection:
        events.append(("connect", url))
        return FakeConnection()

    def fake_run(command: list[str], check: bool) -> None:
        events.append(("run", command, check))

    monkeypatch.setattr("app.core.migration_runner.psycopg.connect", fake_connect)
    monkeypatch.setattr(subprocess, "run", fake_run)

    run_migrations_with_lock(settings=settings, command=("alembic", "upgrade", "head"))

    assert events == [
        ("connect", "postgresql://good_news:phase3-secret@localhost:5432/good_news"),
        ("SELECT pg_advisory_lock(%s)", (ALEMBIC_LOCK_ID,)),
        ("run", ["alembic", "upgrade", "head"], True),
        ("SELECT pg_advisory_unlock(%s)", (ALEMBIC_LOCK_ID,)),
        "closed",
    ]


def test_default_migration_command_targets_repo_alembic_ini() -> None:
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"

    assert default_migration_command() == ("alembic", "-c", str(alembic_ini), "upgrade", "head")

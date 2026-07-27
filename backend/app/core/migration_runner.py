from __future__ import annotations

import subprocess
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path

import psycopg

from app.core.config import Settings

ALEMBIC_LOCK_ID = 2042801
MIGRATION_RUNNER_INVOCATION = "gcloud run jobs execute db-migrate --wait"


def postgres_driver_url(settings: Settings) -> str:
    return settings.database_url().replace("postgresql+psycopg://", "postgresql://", 1)


def default_migration_command() -> tuple[str, str, str, str, str]:
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    return ("alembic", "-c", str(alembic_ini), "upgrade", "head")


@contextmanager
def advisory_migration_lock(settings: Settings):
    connection = psycopg.connect(postgres_driver_url(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (ALEMBIC_LOCK_ID,))
        yield
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (ALEMBIC_LOCK_ID,))
        finally:
            connection.close()


def run_migrations_with_lock(
    settings: Settings | None = None,
    command: Sequence[str] | None = None,
) -> None:
    resolved_settings = settings or Settings.from_env()
    migration_command = list(command or default_migration_command())
    with advisory_migration_lock(resolved_settings):
        subprocess.run(migration_command, check=True)


if __name__ == "__main__":
    run_migrations_with_lock()

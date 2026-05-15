from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.migration_runner import MIGRATION_RUNNER_INVOCATION


class SchemaNotReadyError(RuntimeError):
    """Raised when the database schema is missing or not at Alembic head."""


def expected_revision() -> str:
    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def assert_database_schema_is_current(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        current_revision = _current_revision(session)

    if current_revision != expected_revision():
        raise SchemaNotReadyError(
            f"Database schema is not current; run `{MIGRATION_RUNNER_INVOCATION}`."
        )


def _current_revision(session: Session) -> str:
    try:
        return session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    except Exception as exc:  # pragma: no cover - exercised via startup/API contract tests
        raise SchemaNotReadyError(
            f"Database schema is not current; run `{MIGRATION_RUNNER_INVOCATION}`."
        ) from exc

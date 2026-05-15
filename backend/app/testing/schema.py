from __future__ import annotations

from sqlalchemy import text

from app.core.db import session_scope
from app.core.schema_guard import expected_revision


def stamp_schema_head(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        session.execute(text("DELETE FROM alembic_version"))
        session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": expected_revision()},
        )

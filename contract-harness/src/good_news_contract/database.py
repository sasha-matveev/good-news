from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, url: str) -> None:
        self._url = url

    def seed(self, seed_file: Path) -> None:
        with psycopg.connect(self._url, autocommit=True) as connection:
            connection.execute(seed_file.read_text(encoding="utf-8"))

    def snapshot(self, tables: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
        snapshot = {}
        with psycopg.connect(self._url, row_factory=dict_row) as connection:
            for table in tables:
                primary_key = self._primary_key(connection, table)
                order = f' ORDER BY "{primary_key}"' if primary_key else ""
                rows = connection.execute(f'SELECT * FROM "{table}"{order}').fetchall()
                snapshot[table] = [dict(row) for row in rows]
        return snapshot

    @staticmethod
    def _primary_key(connection: psycopg.Connection, table: str) -> str | None:
        row = connection.execute(
            """
            SELECT attribute.attname
            FROM pg_index index
            JOIN pg_attribute attribute
              ON attribute.attrelid = index.indrelid
             AND attribute.attnum = ANY(index.indkey)
            WHERE index.indrelid = %s::regclass
              AND index.indisprimary
            ORDER BY array_position(index.indkey, attribute.attnum)
            LIMIT 1
            """,
            (table,),
        ).fetchone()
        return row["attname"] if row else None

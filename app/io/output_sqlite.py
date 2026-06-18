# SPDX-License-Identifier: GPL-3.0-or-later
"""SQLite store. One table per profile schema; powers the in-app data viewer
and enables dedupe + historical queries (a roadmap item from the old README)."""

from __future__ import annotations

import re
import sqlite3


def _col(name: str) -> str:
    """Turn a header like 'CHANGE OF DIRECTION' into a safe column name."""
    return re.sub(r"\W+", "_", name.strip().lower()).strip("_")


class SQLiteStore:
    def __init__(self, db_path: str, table: str, headers: list[str]):
        self.table = re.sub(r"\W+", "_", table)
        self.headers = headers
        self.columns = [_col(h) for h in headers]
        self.conn = sqlite3.connect(db_path)
        self._ensure_table()

    def _ensure_table(self):
        cols = ", ".join(f'"{c}" TEXT' for c in self.columns)
        self.conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{self.table}" '
            f"(id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})"
        )
        self.conn.commit()

    def save_row(self, row: list):
        placeholders = ", ".join("?" for _ in self.columns)
        cols = ", ".join(f'"{c}"' for c in self.columns)
        self.conn.execute(
            f'INSERT INTO "{self.table}" ({cols}) VALUES ({placeholders})',
            [str(v) for v in row],
        )
        self.conn.commit()

    def all_rows(self) -> list[tuple]:
        cur = self.conn.execute(
            f'SELECT {", ".join(chr(34) + c + chr(34) for c in self.columns)} '
            f'FROM "{self.table}"'
        )
        return cur.fetchall()

    def close(self):
        self.conn.close()

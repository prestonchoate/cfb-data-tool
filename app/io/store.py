# SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical SQLite store for scraped records.

Every saved scan upserts here (one table per profile), de-duplicated on the
profile's ``dedupe_keys`` (e.g. NAME+POSITION) so re-scanning a recruit updates
the existing row instead of appending a duplicate — the append-only problem the
original CSV flow had. The Data tab reads from this store; CSV is the export format.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path


def col_name(header: str) -> str:
    """Turn a schema header like 'CHANGE OF DIRECTION' into a safe column name."""
    return re.sub(r"\W+", "_", header.strip().lower()).strip("_")


class RecordStore:
    def __init__(self, db_path, profile):
        self.profile = profile
        self.table = re.sub(r"\W+", "_", profile.key)
        self.headers = list(profile.schema)
        self.columns = [col_name(h) for h in self.headers]
        self.dedupe = [col_name(k) for k in profile.dedupe_keys]
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self):
        cols = ", ".join(f'"{c}" TEXT' for c in self.columns)
        unique = ", ".join(f'"{c}"' for c in self.dedupe)
        self.conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{self.table}" '
            f"(id INTEGER PRIMARY KEY AUTOINCREMENT, {cols}, scanned_at TEXT, "
            f"UNIQUE({unique}))"
        )
        self.conn.commit()

    def upsert(self, row: list) -> str:
        """Insert a row (aligned to profile.schema) or update the matching record.

        Returns "inserted" or "updated".
        """
        key_idx = [self.headers.index(k) for k in self.profile.dedupe_keys]
        key_vals = [str(row[i]) for i in key_idx]
        where = " AND ".join(f'"{c}"=?' for c in self.dedupe)
        existed = self.conn.execute(
            f'SELECT 1 FROM "{self.table}" WHERE {where}', key_vals
        ).fetchone() is not None

        cols = self.columns + ["scanned_at"]
        values = [str(v) for v in row] + [datetime.now().isoformat(timespec="seconds")]
        collist = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        updates = ", ".join(f'"{c}"=excluded."{c}"' for c in cols if c not in self.dedupe)
        conflict = ", ".join(f'"{c}"' for c in self.dedupe)
        self.conn.execute(
            f'INSERT INTO "{self.table}" ({collist}) VALUES ({placeholders}) '
            f"ON CONFLICT({conflict}) DO UPDATE SET {updates}",
            values,
        )
        self.conn.commit()
        return "updated" if existed else "inserted"

    def all(self) -> list[dict]:
        cur = self.conn.execute(f'SELECT * FROM "{self.table}" ORDER BY id')
        return [dict(r) for r in cur.fetchall()]

    def delete(self, row_id: int):
        self.conn.execute(f'DELETE FROM "{self.table}" WHERE id=?', (row_id,))
        self.conn.commit()

    def clear(self):
        self.conn.execute(f'DELETE FROM "{self.table}"')
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute(f'SELECT COUNT(*) FROM "{self.table}"').fetchone()[0]

    def close(self):
        self.conn.close()

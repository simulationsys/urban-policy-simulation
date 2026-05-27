"""SQLite-backed scenario registry (PROJECT_SPEC §5.3: SQLite for metadata, no Postgres in v1).

Stores the durable record of each scenario — its config, status, and tick — so the scenario list
survives a process restart even though live tick buffers (state.py) do not. Sim *outputs* go to
Parquet elsewhere; this is just metadata.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.models.schemas import ScenarioConfig, ScenarioStatus, ScenarioSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL,
    config_json  TEXT NOT NULL,
    current_tick INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MetadataStore:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _next_id(self) -> str:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM scenarios").fetchone()
        return f"scenario_{row['n'] + 1:04d}"

    def create(self, config: ScenarioConfig) -> ScenarioSummary:
        sid = self._next_id()
        now = _now()
        self._conn.execute(
            "INSERT INTO scenarios"
            " (id, name, status, config_json, current_tick, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 0, ?, ?)",
            (sid, config.name, ScenarioStatus.created.value, config.model_dump_json(), now, now),
        )
        self._conn.commit()
        return self._row_to_summary(self._fetch_row(sid))

    def list(self) -> list[ScenarioSummary]:
        rows = self._conn.execute("SELECT * FROM scenarios ORDER BY created_at DESC").fetchall()
        return [self._row_to_summary(r) for r in rows]

    def get(self, scenario_id: str) -> ScenarioSummary | None:
        row = self._fetch_row(scenario_id)
        return self._row_to_summary(row) if row else None

    def update_status(self, scenario_id: str, status: ScenarioStatus) -> None:
        self._conn.execute(
            "UPDATE scenarios SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, _now(), scenario_id),
        )
        self._conn.commit()

    def update_tick(self, scenario_id: str, tick: int) -> None:
        self._conn.execute(
            "UPDATE scenarios SET current_tick = ?, updated_at = ? WHERE id = ?",
            (tick, _now(), scenario_id),
        )
        self._conn.commit()

    def delete(self, scenario_id: str) -> None:
        self._conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        self._conn.commit()

    # --- helpers ---
    def _fetch_row(self, scenario_id: str) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()

    @staticmethod
    def _row_to_summary(row: sqlite3.Row) -> ScenarioSummary:
        return ScenarioSummary(
            id=row["id"],
            name=row["name"],
            status=ScenarioStatus(row["status"]),
            config=ScenarioConfig.model_validate(json.loads(row["config_json"])),
            current_tick=row["current_tick"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

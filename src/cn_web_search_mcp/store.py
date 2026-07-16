"""SQLite-backed durable job state, artifacts, and bounded fetch cache."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, database_path: str | Path, artifacts_dir: str | Path):
        self.database_path = Path(database_path)
        self.artifacts_dir = Path(artifacts_dir)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    round_number INTEGER NOT NULL DEFAULT 0,
                    sources_completed INTEGER NOT NULL DEFAULT 0,
                    sources_total INTEGER NOT NULL DEFAULT 0,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE TABLE IF NOT EXISTS fetch_cache (
                    url TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS domain_health (
                    domain TEXT PRIMARY KEY,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    average_elapsed_ms REAL NOT NULL DEFAULT 0,
                    last_status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "UPDATE jobs SET status='failed', phase='interrupted', error='server restarted before job completion', updated_at=? WHERE status IN ('queued','running')",
                (_now(),),
            )

    def create_job(self, job_id: str, request: dict[str, Any]) -> None:
        now = _now()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO jobs(job_id,status,phase,request_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, "queued", "queued", json.dumps(request, ensure_ascii=False), now, now),
            )

    def update_job(self, job_id: str, **changes: Any) -> None:
        allowed = {
            "status", "phase", "round_number", "sources_completed", "sources_total",
            "result_json", "error", "cancel_requested",
        }
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"unsupported job fields: {sorted(invalid)}")
        if "result_json" in changes and isinstance(changes["result_json"], dict):
            changes["result_json"] = json.dumps(changes["result_json"], ensure_ascii=False)
        changes["updated_at"] = _now()
        assignments = ", ".join(f"{key}=?" for key in changes)
        values = [*changes.values(), job_id]
        with self._connection() as connection:
            cursor = connection.execute(f"UPDATE jobs SET {assignments} WHERE job_id=?", values)
            if cursor.rowcount != 1:
                raise KeyError(f"unknown job: {job_id}")

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown job: {job_id}")
        data = dict(row)
        data["request"] = json.loads(data.pop("request_json"))
        result_json = data.pop("result_json")
        data["result"] = json.loads(result_json) if result_json else None
        data["cancel_requested"] = bool(data["cancel_requested"])
        return data

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job["status"] in {"completed", "unresolvable", "failed", "cancelled"}:
            return job
        self.update_job(job_id, cancel_requested=1, phase="cancelling")
        return self.get_job(job_id)

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute("SELECT cancel_requested FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return bool(row and row[0])

    def save_artifact(self, job_id: str, name: str, payload: dict[str, Any]) -> Path:
        directory = self.artifacts_dir / job_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return path

    def read_artifact(self, job_id: str, name: str) -> dict[str, Any]:
        path = self.artifacts_dir / job_id / name
        if not path.exists():
            raise KeyError(f"artifact not found: {job_id}/{name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def cache_get(self, url: str, max_age_seconds: int) -> dict | None:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM fetch_cache WHERE url=? AND fetched_at>=?",
                (url, cutoff),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def cache_put(self, url: str, payload: dict) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO fetch_cache(url,payload_json,fetched_at) VALUES(?,?,?) ON CONFLICT(url) DO UPDATE SET payload_json=excluded.payload_json,fetched_at=excluded.fetched_at",
                (url, json.dumps(payload, ensure_ascii=False), _now()),
            )

    def domain_health_get(self, domain: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM domain_health WHERE domain=?", (domain,)).fetchone()
        return dict(row) if row else None

    def domain_health_record(self, domain: str, status: str, elapsed_ms: int) -> None:
        success = 1 if status == "success" else 0
        blocked = 1 if status == "blocked" else 0
        error = 1 if status in {"error", "empty", "timeout"} else 0
        now = _now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO domain_health(domain,attempts,successes,blocked,errors,average_elapsed_ms,last_status,updated_at)
                VALUES(?,1,?,?,?,?,?,?)
                ON CONFLICT(domain) DO UPDATE SET
                    attempts=domain_health.attempts+1,
                    successes=domain_health.successes+excluded.successes,
                    blocked=domain_health.blocked+excluded.blocked,
                    errors=domain_health.errors+excluded.errors,
                    average_elapsed_ms=((domain_health.average_elapsed_ms*domain_health.attempts)+excluded.average_elapsed_ms)/(domain_health.attempts+1),
                    last_status=excluded.last_status,
                    updated_at=excluded.updated_at
                """,
                (domain, success, blocked, error, float(elapsed_ms), status, now),
            )

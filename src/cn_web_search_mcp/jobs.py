"""Background job façade used by MCP tools."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from typing import Any
from uuid import uuid4

from .config import Settings
from .research import ResearchCancelled, ResearchRunner
from .store import JobStore


_TERMINAL = {"completed", "unresolvable", "failed", "cancelled"}


class JobService:
    def __init__(self, settings: Settings, store: JobStore | None = None, runner: ResearchRunner | None = None):
        settings.prepare()
        self.settings = settings
        self.store = store or JobStore(settings.data_dir / "jobs.sqlite3", settings.data_dir / "artifacts")
        self.runner = runner or ResearchRunner(settings, self.store)
        self.executor = ThreadPoolExecutor(max_workers=settings.max_job_workers, thread_name_prefix="cnws")
        self._events: dict[str, Event] = {}
        self._lock = Lock()

    def start(self, request: dict[str, Any]) -> dict[str, Any]:
        question = str(request.get("question", "")).strip()
        if not question:
            raise ValueError("question must not be empty")
        normalized = {
            "question": question,
            "requirements": request.get("requirements") or [],
            "cutoff_at": request.get("cutoff_at"),
            "timezone": request.get("timezone") or "Asia/Shanghai",
            "profile": request.get("profile") or "balanced",
            "max_rounds": request.get("max_rounds") or 3,
        }
        job_id = f"rs_{uuid4().hex}"
        event = Event()
        with self._lock:
            self._events[job_id] = event
        self.store.create_job(job_id, normalized)
        self.executor.submit(self._execute, job_id, normalized, event)
        return {"job_id": job_id, "status": "queued"}

    def _execute(self, job_id: str, request: dict[str, Any], event: Event) -> None:
        try:
            self.store.update_job(job_id, status="running", phase="planning")

            def progress(phase: str, round_number: int, completed: int, total: int) -> None:
                self.store.update_job(
                    job_id,
                    phase=phase,
                    round_number=round_number,
                    sources_completed=completed,
                    sources_total=total,
                )

            def cancelled() -> bool:
                return event.is_set() or self.store.is_cancel_requested(job_id)

            result = self.runner.run(
                request,
                progress=progress,
                cancelled=cancelled,
                artifact_prefix=job_id,
            )
            self.store.update_job(
                job_id,
                status=result["status"],
                phase="finished",
                result_json=result,
            )
        except ResearchCancelled:
            self.store.update_job(job_id, status="cancelled", phase="finished", error="research job was cancelled")
        except Exception as exc:
            self.store.update_job(job_id, status="failed", phase="finished", error=str(exc))
        finally:
            with self._lock:
                self._events.pop(job_id, None)

    def status(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        return {
            "job_id": job_id,
            "status": job["status"],
            "phase": job["phase"],
            "round": job["round_number"],
            "sources_completed": job["sources_completed"],
            "sources_total": job["sources_total"],
            "error": job["error"] if job["status"] == "failed" else None,
            "updated_at": job["updated_at"],
        }

    def result(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if job["status"] not in _TERMINAL:
            return {
                "job_id": job_id,
                "status": job["status"],
                "phase": job["phase"],
                "result": None,
            }
        return {
            "job_id": job_id,
            "status": job["status"],
            "result": job["result"],
            "error": job["error"],
        }

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self.store.request_cancel(job_id)
        with self._lock:
            event = self._events.get(job_id)
            if event:
                event.set()
        return {"job_id": job_id, "status": job["status"], "cancel_requested": True}

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

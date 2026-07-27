"""Single-customer commercial policy for one dedicated API instance."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4

from .config import Settings
from .jobs import JobService


PROFILE_CREDITS = {"fast": 1, "balanced": 2, "thorough": 4}


class CommercialLimitError(RuntimeError):
    def __init__(
        self,
        code: str,
        detail: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds


def _period_start() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


class CommercialPolicy:
    """Enforce one customer's plan before a research job is accepted."""

    def __init__(self, settings: Settings, service: JobService) -> None:
        if not settings.commercial_mode:
            raise ValueError("commercial policy requires CNWS_COMMERCIAL_MODE")
        if not settings.api_bearer_token:
            raise ValueError("commercial policy requires an API bearer token")
        if (
            settings.monthly_credit_quota < 1
            or settings.rate_limit_per_minute < 1
            or settings.max_active_jobs < 1
        ):
            raise ValueError("commercial policy requires positive plan limits")
        self.settings = settings
        self.service = service
        self._accepted_at: deque[float] = deque()
        self._lock = Lock()

    def _enforce_rate(self, now: float) -> None:
        cutoff = now - 60
        while self._accepted_at and self._accepted_at[0] <= cutoff:
            self._accepted_at.popleft()
        if len(self._accepted_at) >= self.settings.rate_limit_per_minute:
            retry_after = max(1, round(60 - (now - self._accepted_at[0])))
            raise CommercialLimitError(
                "rate_limit_exceeded",
                "research creation rate limit exceeded",
                retry_after_seconds=retry_after,
            )

    def start(self, request: dict[str, Any]) -> dict[str, Any]:
        profile = str(request.get("profile", "balanced")).casefold()
        credits = PROFILE_CREDITS[profile]
        event_id = f"use_{uuid4().hex}"
        with self._lock:
            now = monotonic()
            self._enforce_rate(now)
            if self.service.store.count_active_jobs() >= self.settings.max_active_jobs:
                raise CommercialLimitError(
                    "concurrency_limit_exceeded",
                    "maximum active research jobs reached",
                    retry_after_seconds=2,
                )
            try:
                used = self.service.store.reserve_commercial_usage(
                    event_id=event_id,
                    customer_id=self.settings.customer_id,
                    plan=self.settings.customer_plan,
                    profile=profile,
                    credits=credits,
                    quota=self.settings.monthly_credit_quota,
                    period_start=_period_start(),
                )
            except ValueError as exc:
                raise CommercialLimitError(
                    "monthly_quota_exceeded",
                    "monthly research credit quota exceeded",
                ) from exc
            try:
                started = self.service.start(request)
                self.service.store.bind_commercial_usage(
                    event_id, started["job_id"]
                )
            except Exception:
                self.service.store.release_commercial_usage(event_id)
                raise
            self._accepted_at.append(now)
        return {
            **started,
            "billing": {
                "customer_id": self.settings.customer_id,
                "plan": self.settings.customer_plan,
                "credits_charged": credits,
                "credits_used": used,
                "credits_remaining": self.settings.monthly_credit_quota - used,
            },
        }

    def usage(self) -> dict[str, Any]:
        period_start = _period_start()
        summary = self.service.store.commercial_usage_summary(
            customer_id=self.settings.customer_id,
            period_start=period_start,
        )
        used = summary["credits"]
        return {
            "commercial_mode": True,
            "customer_id": self.settings.customer_id,
            "plan": self.settings.customer_plan,
            "period_start": period_start,
            "monthly_credit_quota": self.settings.monthly_credit_quota,
            "credits_used": used,
            "credits_remaining": max(
                0, self.settings.monthly_credit_quota - used
            ),
            "jobs_created": summary["jobs"],
            "profiles": summary["profiles"],
            "rate_limit_per_minute": self.settings.rate_limit_per_minute,
            "max_active_jobs": self.settings.max_active_jobs,
            "active_jobs": self.service.store.count_active_jobs(),
            "credit_weights": PROFILE_CREDITS,
        }

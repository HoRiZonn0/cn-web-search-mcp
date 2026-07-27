from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cn_web_search_mcp.api import create_api_app
from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.store import JobStore


class FakeJobService:
    def __init__(self):
        self.requests = []
        self.closed = False

    def start(self, request):
        self.requests.append(request)
        return {"job_id": "rs_test", "status": "queued"}

    def status(self, job_id):
        if job_id == "missing":
            raise KeyError(f"unknown job: {job_id}")
        return {
            "job_id": job_id,
            "status": "running",
            "phase": "searching",
            "round": 1,
            "sources_completed": 2,
            "sources_total": 4,
            "error": None,
            "updated_at": "2026-07-23T09:00:00+08:00",
        }

    def result(self, job_id):
        if job_id == "missing":
            raise KeyError(f"unknown job: {job_id}")
        if job_id == "pending":
            return {
                "job_id": job_id,
                "status": "running",
                "phase": "fetching",
                "result": None,
            }
        return {
            "job_id": job_id,
            "status": "completed",
            "result": {
                "question": "测试问题",
                "quality": {"total_score": 90},
                "answer_context": {"facts": []},
            },
            "error": None,
        }

    def cancel(self, job_id):
        if job_id == "missing":
            raise KeyError(f"unknown job: {job_id}")
        return {"job_id": job_id, "status": "running", "cancel_requested": True}

    def close(self):
        self.closed = True


class FakeCommercialService:
    def __init__(self, directory: str):
        root = Path(directory)
        self.store = JobStore(root / "jobs.sqlite3", root / "artifacts")
        self.counter = 0

    def start(self, request):
        self.counter += 1
        job_id = f"rs_commercial_{self.counter}"
        self.store.create_job(job_id, request)
        return {"job_id": job_id, "status": "queued"}

    def status(self, job_id):
        job = self.store.get_job(job_id)
        return {
            "job_id": job_id,
            "status": job["status"],
            "phase": job["phase"],
            "round": job["round_number"],
            "sources_completed": job["sources_completed"],
            "sources_total": job["sources_total"],
            "error": None,
            "updated_at": job["updated_at"],
        }

    def result(self, job_id):
        job = self.store.get_job(job_id)
        return {
            "job_id": job_id,
            "status": job["status"],
            "phase": job["phase"],
            "result": job["result"],
        }

    def cancel(self, job_id):
        self.store.update_job(job_id, status="cancelled")
        return {"job_id": job_id, "status": "cancelled", "cancel_requested": True}

    def close(self):
        pass


class ApiTests(unittest.TestCase):
    def settings(self, directory: str, **changes) -> Settings:
        return Settings(data_dir=Path(directory), **changes)

    def commercial_settings(self, directory: str, **changes) -> Settings:
        values = {
            "commercial_mode": True,
            "customer_id": "customer-a",
            "customer_plan": "starter",
            "api_bearer_token": "customer-secret",
            "monthly_credit_quota": 10,
            "rate_limit_per_minute": 10,
            "max_active_jobs": 10,
            **changes,
        }
        return self.settings(directory, **values)

    def test_async_job_lifecycle_and_openapi(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FakeJobService()
            app = create_api_app(self.settings(directory), service)
            with TestClient(app) as client:
                started = client.post(
                    "/v1/research",
                    json={
                        "question": " 查询世界杯赛程 ",
                        "requirements": ["北京时间"],
                        "profile": "balanced",
                        "max_rounds": 2,
                    },
                )
                status_response = client.get("/v1/research/rs_test")
                pending = client.get("/v1/research/pending/result")
                completed = client.get("/v1/research/rs_test/result")
                cancelled = client.delete("/v1/research/rs_test")
                openapi = client.get("/openapi.json")

        self.assertEqual(started.status_code, 202)
        self.assertEqual(started.json()["job_id"], "rs_test")
        self.assertEqual(service.requests[0]["question"], "查询世界杯赛程")
        self.assertEqual(status_response.json()["phase"], "searching")
        self.assertEqual(pending.status_code, 202)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["result"]["quality"]["total_score"], 90)
        self.assertTrue(cancelled.json()["cancel_requested"])
        self.assertIn("/v1/research", openapi.json()["paths"])
        self.assertFalse(service.closed)

    def test_bearer_auth_and_unknown_job(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_api_app(
                self.settings(directory, api_bearer_token="secret-token"),
                FakeJobService(),
            )
            with TestClient(app) as client:
                unauthorized = client.post(
                    "/v1/research", json={"question": "test"}
                )
                authorized = client.post(
                    "/v1/research",
                    json={"question": "test"},
                    headers={"Authorization": "Bearer secret-token"},
                )
                missing = client.get(
                    "/v1/research/missing",
                    headers={"Authorization": "Bearer secret-token"},
                )
                health = client.get("/healthz")

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 202)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(health.json(), {"status": "ok"})

    def test_sync_endpoint_returns_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_api_app(
                self.settings(directory, api_sync_timeout_seconds=1),
                FakeJobService(),
            )
            with TestClient(app) as client:
                response = client.post(
                    "/v1/research/sync",
                    json={"question": "同步测试"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")

    def test_request_validation_rejects_invalid_profile_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_api_app(self.settings(directory), FakeJobService())
            with TestClient(app) as client:
                response = client.post(
                    "/v1/research",
                    json={
                        "question": "test",
                        "profile": "unlimited",
                        "unexpected": True,
                    },
                )

        self.assertEqual(response.status_code, 422)

    def test_app_factory_rejects_unprotected_remote_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                ValueError, "requires CNWS_API_BEARER_TOKEN"
            ):
                create_api_app(
                    self.settings(directory, api_host="0.0.0.0"),
                    FakeJobService(),
                )

    def test_commercial_instance_charges_profile_credits_and_reports_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FakeCommercialService(directory)
            app = create_api_app(self.commercial_settings(directory), service)
            headers = {"Authorization": "Bearer customer-secret"}
            with TestClient(app) as client:
                started = client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "商业搜索", "profile": "thorough"},
                )
                usage = client.get("/v1/account/usage", headers=headers)

        self.assertEqual(started.status_code, 202)
        self.assertEqual(started.json()["billing"]["credits_charged"], 4)
        self.assertEqual(started.json()["billing"]["credits_remaining"], 6)
        self.assertEqual(usage.json()["customer_id"], "customer-a")
        self.assertEqual(usage.json()["credits_used"], 4)
        self.assertEqual(usage.json()["profiles"]["thorough"]["jobs"], 1)

    def test_commercial_monthly_quota_is_atomic_and_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.commercial_settings(
                directory, monthly_credit_quota=2
            )
            service = FakeCommercialService(directory)
            headers = {"Authorization": "Bearer customer-secret"}
            with TestClient(create_api_app(settings, service)) as client:
                first = client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "first", "profile": "balanced"},
                )
                second = client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "second", "profile": "fast"},
                )

            restarted_service = FakeCommercialService(directory)
            with TestClient(
                create_api_app(settings, restarted_service)
            ) as restarted:
                usage = restarted.get("/v1/account/usage", headers=headers)

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(
            second.json()["detail"]["code"], "monthly_quota_exceeded"
        )
        self.assertEqual(usage.json()["credits_used"], 2)

    def test_commercial_rate_and_concurrency_limits_return_retry_after(self):
        headers = {"Authorization": "Bearer customer-secret"}
        with tempfile.TemporaryDirectory() as rate_directory:
            rate_settings = self.commercial_settings(
                rate_directory, rate_limit_per_minute=1
            )
            rate_app = create_api_app(
                rate_settings, FakeCommercialService(rate_directory)
            )
            with TestClient(rate_app) as client:
                client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "first"},
                )
                rate_limited = client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "second"},
                )

        with tempfile.TemporaryDirectory() as concurrency_directory:
            concurrency_settings = self.commercial_settings(
                concurrency_directory, max_active_jobs=1
            )
            concurrency_app = create_api_app(
                concurrency_settings,
                FakeCommercialService(concurrency_directory),
            )
            with TestClient(concurrency_app) as client:
                client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "first"},
                )
                concurrency_limited = client.post(
                    "/v1/research",
                    headers=headers,
                    json={"question": "second"},
                )

        self.assertEqual(rate_limited.status_code, 429)
        self.assertEqual(
            rate_limited.json()["detail"]["code"], "rate_limit_exceeded"
        )
        self.assertIn("Retry-After", rate_limited.headers)
        self.assertEqual(concurrency_limited.status_code, 429)
        self.assertEqual(
            concurrency_limited.json()["detail"]["code"],
            "concurrency_limit_exceeded",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cn_web_search_mcp.api import create_api_app
from cn_web_search_mcp.config import Settings


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


class ApiTests(unittest.TestCase):
    def settings(self, directory: str, **changes) -> Settings:
        return Settings(data_dir=Path(directory), **changes)

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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.research import ResearchRunner
from cn_web_search_mcp.store import JobStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one bounded live research smoke test")
    parser.add_argument("question", nargs="?", default="Python 官方网站是什么")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        settings = replace(
            Settings.from_env(),
            data_dir=root,
            max_results_per_source=3,
            max_fetches_per_round=4,
        )
        store = JobStore(root / "jobs.sqlite3", root / "artifacts")
        result = ResearchRunner(settings, store).run(
            {"question": args.question, "profile": "fast", "max_rounds": 1},
            artifact_prefix="smoke",
        )
        payload = store.read_artifact("smoke", "round-1-input.json")
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "quality": result["quality"]["total_score"],
                    "evidence_count": len(result["evidence"]),
                    "stages": payload["stages"],
                    "trace": result["trace_summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

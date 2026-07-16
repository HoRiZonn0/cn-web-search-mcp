"""Validate host/model-detected semantic conflicts without guessing from wording."""

from __future__ import annotations

def normalize_declared_conflicts(items: list[dict]) -> list[dict]:
    """Normalize explicit conflicts; different wording alone is not a conflict."""

    normalized: list[dict] = []
    for item in items:
        if not item.get("requirement_id") or not item.get("claims"):
            continue
        normalized.append(
            {
                "requirement_id": item["requirement_id"],
                "severity": item.get("severity", "critical"),
                "resolved": bool(item.get("resolved", False)),
                "claims": item["claims"],
                "resolution": item.get("resolution", ""),
            }
        )
    return normalized

"""Validated public request models for the REST gateway."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResearchRequest(BaseModel):
    """One autonomous research job submitted over HTTP."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=8_000)
    requirements: list[str] = Field(default_factory=list, max_length=12)
    profile: Literal["fast", "balanced", "thorough"] = "balanced"
    max_rounds: int = Field(default=3, ge=1, le=5)
    cutoff_at: str | None = Field(default=None, max_length=100)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=100)

    @field_validator("requirements")
    @classmethod
    def validate_requirements(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        if any(len(value) > 1_000 for value in normalized):
            raise ValueError("each requirement must be at most 1000 characters")
        return normalized

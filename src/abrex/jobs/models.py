"""Typed contracts for portable, prediction-only resolver jobs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Sha256 = str


class PortableJob(BaseModel):
    """One resolver invocation contained in a portable bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    resolver_key: str = Field(min_length=1)
    config_path: str = Field(min_length=1)
    documents_path: str = Field(min_length=1)
    dataset_fingerprint: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    documents_fingerprint: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    required_capabilities: tuple[str, ...] = ()
    python_executable: str = Field(default="python", min_length=1)
    python_environment: str = Field(
        default="ABREX_JOB_PYTHON", pattern=r"^[A-Z][A-Z0-9_]*$"
    )

    @field_validator("config_path", "documents_path")
    @classmethod
    def relative_bundle_path(cls, value: str) -> str:
        """Reject absolute and traversing paths at the schema boundary."""

        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized.split("/", 1)[0]:
            raise ValueError("bundle paths must be relative")
        if any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("bundle paths must not traverse directories")
        return normalized


class JobBundleManifest(BaseModel):
    """Content-addressed manifest for a portable job bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["job-bundle-v1"] = "job-bundle-v1"
    bundle_id: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    created_utc: str = Field(min_length=1)
    source: dict[str, Any]
    jobs: tuple[PortableJob, ...]
    files: dict[str, Sha256]


class JobResultManifest(BaseModel):
    """Verifiable result for one portable job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["job-result-v1"] = "job-result-v1"
    result_id: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_id: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    job_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    status: Literal["complete", "failed"]
    started_utc: str = Field(min_length=1)
    completed_utc: str = Field(min_length=1)
    elapsed_seconds: float = Field(ge=0)
    dataset_fingerprint: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    documents_fingerprint: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    resolver: dict[str, str]
    environment: dict[str, Any]
    files: dict[str, Sha256]
    error: dict[str, str] | None = None


__all__ = ["JobBundleManifest", "JobResultManifest", "PortableJob"]

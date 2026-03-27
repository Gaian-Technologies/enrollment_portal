"""Typed models for access requests, invite issuance, and health responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

STRICT_MODEL_CONFIG = ConfigDict(extra="forbid")


class AccessRequestCreate(BaseModel):
    """Validated public request payload before verification email delivery."""

    model_config = STRICT_MODEL_CONFIG

    email: EmailStr
    name: str = ""

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 120:
            raise ValueError("name must be 120 characters or fewer")
        return cleaned


class AccessRequestRecord(BaseModel):
    """Persisted access request state."""

    model_config = STRICT_MODEL_CONFIG

    request_id: str
    email: str
    name: str
    client_ip: str
    status: Literal["pending_verification", "token_issued"]
    token_hash: str
    requested_at: datetime
    verification_expires_at: datetime
    issued_at: datetime | None = None
    invite_id: str | None = None


class InviteIssueResponse(BaseModel):
    """Subset of the `data_hub` admin invite response consumed by the portal."""

    model_config = STRICT_MODEL_CONFIG

    invite_id: str
    enrollment_token: str
    created_at: datetime
    expires_at: datetime | None = None
    used_count: int = Field(default=0)


class HealthResponse(BaseModel):
    """Health response for load balancers and operators."""

    model_config = STRICT_MODEL_CONFIG

    status: Literal["ok"]

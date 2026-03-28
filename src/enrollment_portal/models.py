"""Typed models for access requests, verification codes, and invite issuance."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

STRICT_MODEL_CONFIG = ConfigDict(extra="forbid")


def normalize_verification_code(value: str) -> str:
    """Canonicalize user-entered verification codes.

    The portal accepts pasted codes with spaces or hyphens so the email format
    can stay human-readable without affecting the stored hash.
    """

    return "".join(char for char in value.upper() if char.isalnum())


class AccessRequestCreate(BaseModel):
    """Validated public request payload before verification email delivery."""

    model_config = STRICT_MODEL_CONFIG

    email: EmailStr
    name: str = ""
    site_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 120:
            raise ValueError("name must be 120 characters or fewer")
        return cleaned

    @field_validator("site_metadata")
    @classmethod
    def normalize_site_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            str(key).strip(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and str(item).strip()
        }


class AccessRequestRecord(BaseModel):
    """Persisted access request state."""

    model_config = STRICT_MODEL_CONFIG

    request_id: str
    email: str
    name: str
    site_metadata: dict[str, str] = Field(default_factory=dict)
    client_ip: str
    status: Literal["pending_verification", "token_issued"]
    verification_code_hash: str
    requested_at: datetime
    verification_expires_at: datetime
    issued_at: datetime | None = None
    invite_id: str | None = None


class VerificationCodeSubmit(BaseModel):
    """Validated verification-code form payload."""

    model_config = STRICT_MODEL_CONFIG

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        cleaned = normalize_verification_code(value)
        if len(cleaned) != 12:
            raise ValueError("verification code must be 12 characters")
        return cleaned


class InviteIssueResponse(BaseModel):
    """Subset of the `data_hub` admin invite response consumed by the portal."""

    model_config = ConfigDict(extra="ignore")

    invite_id: str
    enrollment_token: str
    created_at: datetime
    expires_at: datetime | None = None
    used_count: int = Field(default=0)


class HealthResponse(BaseModel):
    """Health response for load balancers and operators."""

    model_config = STRICT_MODEL_CONFIG

    status: Literal["ok"]

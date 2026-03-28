"""Environment-backed settings for the supported portal deployment shape."""

from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import quote


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _get_aws_region() -> str:
    for name in ("AWS_REGION", "AWS_DEFAULT_REGION"):
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    raise ValueError("Missing required environment variable: AWS_REGION")


@dataclass(slots=True, frozen=True)
class Settings:
    """Canonical runtime settings loaded from `ENROLLMENT_PORTAL_*` variables."""

    bind_host: str
    bind_port: int
    public_base_url: str
    site_name: str
    hub_admin_api_url: str
    hub_admin_token: str
    db_file: str
    verification_ttl_minutes: int
    invite_expires_hours: int
    rate_limit_per_ip_per_hour: int
    rate_limit_per_email_per_hour: int
    aws_region: str
    ses_from_email: str
    ses_configuration_set: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bind_host=os.getenv("ENROLLMENT_PORTAL_BIND_HOST", "0.0.0.0"),
            bind_port=_get_int("ENROLLMENT_PORTAL_BIND_PORT", 8100),
            public_base_url=_get_required("ENROLLMENT_PORTAL_PUBLIC_BASE_URL").rstrip("/"),
            site_name=os.getenv("ENROLLMENT_PORTAL_SITE_NAME", "Gaian Telemetry").strip(),
            hub_admin_api_url=_get_required("ENROLLMENT_PORTAL_HUB_ADMIN_API_URL").rstrip("/"),
            hub_admin_token=_get_required("ENROLLMENT_PORTAL_HUB_ADMIN_TOKEN"),
            db_file=os.getenv("ENROLLMENT_PORTAL_DB_FILE", "/app/var/access_requests.sqlite3"),
            verification_ttl_minutes=_get_int("ENROLLMENT_PORTAL_VERIFICATION_TTL_MINUTES", 30),
            invite_expires_hours=_get_int("ENROLLMENT_PORTAL_INVITE_EXPIRES_HOURS", 1),
            rate_limit_per_ip_per_hour=_get_int("ENROLLMENT_PORTAL_RATE_LIMIT_PER_IP_PER_HOUR", 10),
            rate_limit_per_email_per_hour=_get_int("ENROLLMENT_PORTAL_RATE_LIMIT_PER_EMAIL_PER_HOUR", 3),
            aws_region=_get_aws_region(),
            ses_from_email=_get_required("ENROLLMENT_PORTAL_SES_FROM_EMAIL"),
            ses_configuration_set=os.getenv("ENROLLMENT_PORTAL_SES_CONFIGURATION_SET", "").strip(),
        )

    def verification_url(self, token: str) -> str:
        return f"{self.public_base_url}/verify?token={quote(token)}"

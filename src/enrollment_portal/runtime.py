"""Runtime orchestration for request intake, code verification, SES delivery, and invite issuance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from .config import Settings
from .emailer import EmailDeliveryError, EmailSender
from .hub_client import HubAdminError, issue_enrollment_invite
from .models import (
    AccessRequestCreate,
    AccessRequestRecord,
    InviteIssueResponse,
    VerificationCodeSubmit,
    normalize_verification_code,
)
from .store import RequestStore


class RateLimitError(Exception):
    """Raised when request issuance exceeds the configured portal limits."""


class VerificationError(Exception):
    """Raised when a verification code is invalid, expired, or already used."""


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


VERIFICATION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_verification_code() -> str:
    """Generate a short human-entered code without visually ambiguous characters."""

    raw = "".join(secrets.choice(VERIFICATION_CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


class PortalRuntime:
    """Coordinate request storage, SES delivery, and Hub invite issuance."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = RequestStore(settings)
        self.emailer = EmailSender(settings)

    async def start(self) -> None:
        await self.store.start()

    async def submit_request(self, payload: AccessRequestCreate, client_ip: str) -> None:
        await self._enforce_rate_limits(payload.email, client_ip)

        verification_code = generate_verification_code()
        requested_at = utcnow()
        record = AccessRequestRecord(
            request_id=secrets.token_hex(12),
            email=str(payload.email).strip().lower(),
            name=payload.name,
            client_ip=client_ip,
            status="pending_verification",
            verification_code_hash=hash_token(normalize_verification_code(verification_code)),
            requested_at=requested_at,
            verification_expires_at=requested_at + timedelta(minutes=self.settings.verification_ttl_minutes),
            issued_at=None,
            invite_id=None,
        )

        await self.store.create_request(record)
        try:
            self.emailer.send_verification_email(
                email=record.email,
                name=record.name,
                verification_code=verification_code,
                verification_page_url=self.settings.verification_page_url(),
            )
        except Exception:
            await self.store.delete_request(record.request_id)
            raise

    async def verify_request(self, payload: VerificationCodeSubmit) -> InviteIssueResponse:
        request = await self.store.get_request_by_verification_code_hash(hash_token(payload.code))
        if request is None:
            raise VerificationError("invalid_or_expired_code")
        if request.status != "pending_verification":
            raise VerificationError("verification_code_already_used")
        if request.verification_expires_at <= utcnow():
            raise VerificationError("invalid_or_expired_code")

        invite = await issue_enrollment_invite(
            self.settings,
            request_id=request.request_id,
            email=request.email,
        )
        await self.store.mark_request_issued(
            request.request_id,
            invite.invite_id,
            utcnow(),
        )
        return invite

    async def _enforce_rate_limits(self, email: str, client_ip: str) -> None:
        window_start = utcnow() - timedelta(hours=1)
        ip_count = await self.store.count_requests_by_ip_since(client_ip, window_start)
        if ip_count >= self.settings.rate_limit_per_ip_per_hour:
            raise RateLimitError("too_many_requests_from_ip")

        email_count = await self.store.count_requests_by_email_since(email.strip().lower(), window_start)
        if email_count >= self.settings.rate_limit_per_email_per_hour:
            raise RateLimitError("too_many_requests_for_email")

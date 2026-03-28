"""Cloudflare Turnstile verification for the public request form."""

from __future__ import annotations

import logging
import secrets

import httpx

from .config import Settings

LOGGER = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class HumanVerificationFailed(Exception):
    """Raised when the submitted Turnstile token is missing or invalid."""


class HumanVerificationUnavailable(Exception):
    """Raised when the Turnstile verification service cannot be reached."""


class TurnstileVerifier:
    """Validate Turnstile tokens server-side before issuing verification emails."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify(self, *, token: str, client_ip: str) -> None:
        cleaned = token.strip()
        if not cleaned:
            raise HumanVerificationFailed("missing_turnstile_token")

        payload = {
            "secret": self._settings.turnstile_secret_key,
            "response": cleaned,
            "remoteip": client_ip,
            "idempotency_key": secrets.token_hex(16),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(TURNSTILE_VERIFY_URL, data=payload)
                response.raise_for_status()
        except httpx.HTTPError as err:
            LOGGER.exception("Failed to verify Turnstile token with Cloudflare")
            raise HumanVerificationUnavailable("turnstile_verification_unavailable") from err

        body = response.json()
        if body.get("success") is True:
            return

        LOGGER.warning(
            "Turnstile validation failed error_codes=%s hostname=%s action=%s",
            body.get("error-codes", []),
            body.get("hostname"),
            body.get("action"),
        )
        raise HumanVerificationFailed("invalid_turnstile_token")

"""Client for the private `data_hub` admin invite endpoint."""

from __future__ import annotations

import httpx

from .config import Settings
from .models import InviteIssueResponse


class HubAdminError(Exception):
    """Raised when the portal cannot issue an invite through `data_hub`."""


def _admin_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.hub_admin_token}",
        "Content-Type": "application/json",
    }


def _site_statuses_url(settings: Settings) -> str:
    if settings.hub_admin_api_url.endswith("/api/v1/admin/invites"):
        return settings.hub_admin_api_url.removesuffix("/api/v1/admin/invites") + "/api/v1/sites"
    raise HubAdminError("invalid_hub_admin_api_url")


async def issue_enrollment_invite(
    settings: Settings,
    *,
    request_id: str,
    email: str,
    site_metadata: dict[str, str],
) -> InviteIssueResponse:
    payload = {
        "note": f"portal:{request_id}:{email}",
        "site_metadata": site_metadata,
        "max_uses": 1,
        "expires_in_hours": settings.invite_expires_hours,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                settings.hub_admin_api_url,
                json=payload,
                headers=_admin_headers(settings),
            )
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise HubAdminError("failed_to_issue_invite") from err

    try:
        return InviteIssueResponse.model_validate(response.json())
    except Exception as err:
        raise HubAdminError("invalid_invite_response") from err


async def list_site_statuses(settings: Settings) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                _site_statuses_url(settings),
                headers=_admin_headers(settings),
            )
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise HubAdminError("failed_to_list_sites") from err

    payload = response.json()
    if not isinstance(payload, list):
        raise HubAdminError("invalid_site_list_response")
    return [item for item in payload if isinstance(item, dict)]

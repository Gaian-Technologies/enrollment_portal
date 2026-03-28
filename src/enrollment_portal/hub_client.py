"""Client for the private `data_hub` admin invite endpoint."""

from __future__ import annotations

import httpx

from .config import Settings
from .models import InviteIssueResponse


class HubAdminError(Exception):
    """Raised when the portal cannot issue an invite through `data_hub`."""


async def issue_enrollment_invite(
    settings: Settings,
    *,
    request_id: str,
    email: str,
) -> InviteIssueResponse:
    payload = {
        "note": f"portal:{request_id}:{email}",
        "max_uses": 1,
        "expires_in_hours": settings.invite_expires_hours,
    }
    headers = {
        "Authorization": f"Bearer {settings.hub_admin_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                settings.hub_admin_api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise HubAdminError("failed_to_issue_invite") from err

    try:
        return InviteIssueResponse.model_validate(response.json())
    except Exception as err:
        raise HubAdminError("invalid_invite_response") from err

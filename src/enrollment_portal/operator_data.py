"""Internal-only operator dashboard rows joined from portal and Hub state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import AccessRequestRecord


@dataclass(slots=True, frozen=True)
class OperatorRequestRow:
    request_id: str
    requested_at: datetime
    issued_at: datetime | None
    status: str
    request_mode: str
    email: str
    name: str
    country: str
    property_roles: str
    site_reference_scheme: str
    site_reference_value: str
    metadata_summary: str
    invite_id: str
    site_id: str
    connected: bool
    last_telemetry_at: str
    last_heartbeat_at: str


@dataclass(slots=True, frozen=True)
class OperatorDashboard:
    total_requests: int
    verified_people: int
    token_issued: int
    interest_registered: int
    linked_sites: int
    connected_sites: int
    rows: tuple[OperatorRequestRow, ...]


def build_operator_dashboard(
    requests: list[AccessRequestRecord],
    site_statuses: list[dict],
) -> OperatorDashboard:
    sites_by_invite = _index_sites_by_invite(site_statuses)
    rows: list[OperatorRequestRow] = []
    verified_emails: set[str] = set()
    token_issued = 0
    interest_registered = 0
    linked_sites = 0
    connected_sites = 0

    for record in requests:
        if record.status in {"interest_registered", "token_issued"}:
            verified_emails.add(record.email.strip().lower())
        if record.status == "token_issued":
            token_issued += 1
        elif record.status == "interest_registered":
            interest_registered += 1

        linked_site = sites_by_invite.get(record.invite_id or "")
        if linked_site is not None:
            linked_sites += 1
            if linked_site["connected"]:
                connected_sites += 1

        metadata = dict(record.site_metadata)
        country = metadata.pop("country", "")
        property_roles = metadata.pop("property_roles", "")
        site_reference_scheme = metadata.pop("site_reference_scheme", "")
        site_reference_value = metadata.pop("site_reference_value", "")
        metadata_summary = "; ".join(f"{key}: {value}" for key, value in sorted(metadata.items()))

        rows.append(
            OperatorRequestRow(
                request_id=record.request_id,
                requested_at=record.requested_at,
                issued_at=record.issued_at,
                status=record.status,
                request_mode=record.request_mode,
                email=record.email,
                name=record.name,
                country=country,
                property_roles=property_roles.replace(" | ", ", "),
                site_reference_scheme=site_reference_scheme,
                site_reference_value=site_reference_value,
                metadata_summary=metadata_summary,
                invite_id=record.invite_id or "",
                site_id=linked_site["site_id"] if linked_site is not None else "",
                connected=linked_site["connected"] if linked_site is not None else False,
                last_telemetry_at=linked_site["last_telemetry_at"] if linked_site is not None else "",
                last_heartbeat_at=linked_site["last_heartbeat_at"] if linked_site is not None else "",
            )
        )

    return OperatorDashboard(
        total_requests=len(requests),
        verified_people=len(verified_emails),
        token_issued=token_issued,
        interest_registered=interest_registered,
        linked_sites=linked_sites,
        connected_sites=connected_sites,
        rows=tuple(rows),
    )


def _index_sites_by_invite(site_statuses: list[dict]) -> dict[str, dict[str, str | bool]]:
    indexed: dict[str, dict[str, str | bool]] = {}
    for status in site_statuses:
        registration = status.get("registration")
        if not isinstance(registration, dict):
            continue
        invite_id = str(registration.get("invite_id", "") or "").strip()
        if not invite_id:
            continue
        runtime = status.get("runtime")
        reported = runtime.get("reported") if isinstance(runtime, dict) else None
        connected = False
        if isinstance(reported, dict):
            connected = bool(reported.get("connected"))
        if not connected and isinstance(runtime, dict):
            connected = bool(runtime.get("last_telemetry_at"))
        indexed[invite_id] = {
            "site_id": str(status.get("site_id", "") or "").strip(),
            "connected": connected,
            "last_telemetry_at": _string_or_empty(runtime.get("last_telemetry_at")) if isinstance(runtime, dict) else "",
            "last_heartbeat_at": _string_or_empty(runtime.get("last_heartbeat_at")) if isinstance(runtime, dict) else "",
        }
    return indexed


def _string_or_empty(value: object) -> str:
    return str(value).strip() if value is not None and str(value).strip() else ""

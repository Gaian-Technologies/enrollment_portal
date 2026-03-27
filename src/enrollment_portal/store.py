"""SQLite-backed request store for email-verified token issuance."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import sqlite3

from .config import Settings
from .models import AccessRequestRecord


class RequestStore:
    """Persist public access requests separately from the Hub runtime."""

    def __init__(self, settings: Settings) -> None:
        self._db_path = Path(settings.db_file)
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        await asyncio.to_thread(self._initialize)

    async def create_request(self, record: AccessRequestRecord) -> None:
        async with self._lock:
            await asyncio.to_thread(self._insert_request, record)

    async def delete_request(self, request_id: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._delete_request_sync, request_id)

    async def get_request_by_token_hash(self, token_hash: str) -> AccessRequestRecord | None:
        async with self._lock:
            row = await asyncio.to_thread(self._fetch_request_by_token_hash_sync, token_hash)
        if row is None:
            return None
        return AccessRequestRecord.model_validate(row)

    async def mark_request_issued(
        self,
        request_id: str,
        invite_id: str,
        issued_at: datetime,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._mark_request_issued_sync,
                request_id,
                invite_id,
                issued_at.isoformat(),
            )

    async def count_requests_by_ip_since(self, client_ip: str, requested_after: datetime) -> int:
        async with self._lock:
            return await asyncio.to_thread(
                self._count_requests_by_ip_since_sync,
                client_ip,
                requested_after.isoformat(),
            )

    async def count_requests_by_email_since(self, email: str, requested_after: datetime) -> int:
        async with self._lock:
            return await asyncio.to_thread(
                self._count_requests_by_email_since_sync,
                email,
                requested_after.isoformat(),
            )

    def _initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS access_requests (
                    request_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    status TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    requested_at TEXT NOT NULL,
                    verification_expires_at TEXT NOT NULL,
                    issued_at TEXT,
                    invite_id TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_access_requests_email ON access_requests(email)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_access_requests_ip ON access_requests(client_ip)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_access_requests_requested_at ON access_requests(requested_at)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _insert_request(self, record: AccessRequestRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO access_requests (
                    request_id,
                    email,
                    name,
                    client_ip,
                    status,
                    token_hash,
                    requested_at,
                    verification_expires_at,
                    issued_at,
                    invite_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.request_id,
                    record.email,
                    record.name,
                    record.client_ip,
                    record.status,
                    record.token_hash,
                    record.requested_at.isoformat(),
                    record.verification_expires_at.isoformat(),
                    record.issued_at.isoformat() if record.issued_at else None,
                    record.invite_id,
                ),
            )
            connection.commit()

    def _delete_request_sync(self, request_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM access_requests WHERE request_id = ?",
                (request_id,),
            )
            connection.commit()

    def _fetch_request_by_token_hash_sync(self, token_hash: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT request_id, email, name, client_ip, status, token_hash,
                       requested_at, verification_expires_at, issued_at, invite_id
                FROM access_requests
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        return dict(row) if row is not None else None

    def _mark_request_issued_sync(self, request_id: str, invite_id: str, issued_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE access_requests
                SET status = ?, invite_id = ?, issued_at = ?
                WHERE request_id = ?
                """,
                ("token_issued", invite_id, issued_at, request_id),
            )
            connection.commit()

    def _count_requests_by_ip_since_sync(self, client_ip: str, requested_after: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM access_requests
                WHERE client_ip = ? AND requested_at >= ?
                """,
                (client_ip, requested_after),
            ).fetchone()
        return int(row[0])

    def _count_requests_by_email_since_sync(self, email: str, requested_after: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM access_requests
                WHERE email = ? AND requested_at >= ?
                """,
                (email, requested_after),
            ).fetchone()
        return int(row[0])

"""ArcadeDB HTTP client for Agent Operations.

Provides an async client for interacting with ArcadeDB via its HTTP/JSON API.
Supports query execution, command execution, and health checks.
"""

from __future__ import annotations

from typing import Any

import httpx


class ArcadeDBError(Exception):
    """Base exception for ArcadeDB client errors."""


class ArcadeDBConnectionError(ArcadeDBError):
    """Connection failure to ArcadeDB server."""


class ArcadeDBQueryError(ArcadeDBError):
    """ArcadeDB returned an error for a query or command."""


class ArcadeDBClient:
    """Async HTTP client for ArcadeDB."""

    def __init__(
        self,
        url: str,
        database: str,
        user: str,
        password: str,
        timeout: float = 30.0,
    ) -> None:
        self._url = url.rstrip("/")
        self._database = database
        self._client = httpx.AsyncClient(
            auth=(user, password),
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Execute a read-only (idempotent) query.

        Args:
            query: The SQL query string with :paramName placeholders
            params: Optional parameter map
            limit: Maximum number of records to return

        Returns:
            List of result records

        Raises:
            ArcadeDBConnectionError: On connection failure
            ArcadeDBQueryError: On server-reported error
        """
        body: dict[str, Any] = {"language": "sql", "command": query, "limit": limit}
        if params:
            body["params"] = params

        try:
            response = await self._client.post(
                f"{self._url}/api/v1/query/{self._database}",
                json=body,
            )
        except httpx.RequestError as e:
            raise ArcadeDBConnectionError(f"Failed to connect to ArcadeDB: {e}") from e

        data = response.json()
        if not response.is_success:
            raise ArcadeDBQueryError(
                f"Query failed (HTTP {response.status_code}): {data}"
            )
        result = data.get("result", [])
        return list(result) if isinstance(result, list) else []

    async def execute_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a non-idempotent command (insert, update, create, etc.).

        Args:
            command: The SQL command string with :paramName placeholders
            params: Optional parameter map

        Returns:
            List of result records

        Raises:
            ArcadeDBConnectionError: On connection failure
            ArcadeDBQueryError: On server-reported error
        """
        body: dict[str, Any] = {"language": "sql", "command": command}
        if params:
            body["params"] = params

        try:
            response = await self._client.post(
                f"{self._url}/api/v1/command/{self._database}",
                json=body,
            )
        except httpx.RequestError as e:
            raise ArcadeDBConnectionError(f"Failed to connect to ArcadeDB: {e}") from e

        data = response.json()
        if not response.is_success:
            raise ArcadeDBQueryError(
                f"Command failed (HTTP {response.status_code}): {data}"
            )
        result = data.get("result", [])
        return list(result) if isinstance(result, list) else []

    async def health_check(self) -> bool:
        """Check if the ArcadeDB server is reachable and healthy.

        Returns:
            True if server responds successfully
        """
        try:
            response = await self._client.get(f"{self._url}/api/v1/ready")
            return response.is_success
        except httpx.RequestError:
            return False

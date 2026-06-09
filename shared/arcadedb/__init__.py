"""ArcadeDB client package — HTTP API client and domain operations."""

from .client import (
    ArcadeDBClient,
    ArcadeDBConnectionError,
    ArcadeDBError,
    ArcadeDBQueryError,
)

__all__ = [
    "ArcadeDBClient",
    "ArcadeDBConnectionError",
    "ArcadeDBError",
    "ArcadeDBQueryError",
]

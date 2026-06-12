"""Commitment status constants.

Shared by agents and functions to avoid magic strings for ArcadeDB queries.
"""

from typing import Final

# Core lifecycle
PENDING: Final = "pending"
ACTIVE: Final = "active"

# Approval gate
PENDING_APPROVAL: Final = "pending_approval"
APPROVED: Final = "approved"
REJECTED: Final = "rejected"
DEFERRED: Final = "deferred"

# Execution
EXECUTING: Final = "executing"

# Terminal
COMPLETE: Final = "complete"
STALLED: Final = "stalled"
ESCALATED: Final = "escalated"

# Implementation sub-state
TO_DO: Final = "to_do"
IN_PROGRESS: Final = "in_progress"
FAILED: Final = "failed"

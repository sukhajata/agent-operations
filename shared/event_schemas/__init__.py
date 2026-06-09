"""Event schema validation — canonical event emission gate."""

from .validator import EventSchemaError, check_required_fields, emit_validated, validate_event

__all__ = [
    "EventSchemaError",
    "check_required_fields",
    "emit_validated",
    "validate_event",
]

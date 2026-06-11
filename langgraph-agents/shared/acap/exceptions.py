"""ACAP enforcement exceptions."""


class ACAPViolationError(Exception):
    """Raised when an agent action violates its ACAP constraints.

    Logged to the event log before the exception propagates, so violations
    are always tracked even if the caller catches the error.
    """

    def __init__(
        self,
        action: str,
        reason: str,
        agent_id: str,
        focus_id: str,
    ) -> None:
        self.action = action
        self.reason = reason
        self.agent_id = agent_id
        self.focus_id = focus_id
        super().__init__(f"ACAP violation by {agent_id}: {action} — {reason}")


class ScopeViolationError(ACAPViolationError):
    """An agent attempted an action outside its permitted scope.

    More severe than a general ACAP violation — indicates an agent may
    be malfunctioning or misconfigured.
    """

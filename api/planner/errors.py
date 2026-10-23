"""Domain errors."""


class PlanningError(ValueError):
    """The request is well-formed but cannot be planned (e.g. past date)."""

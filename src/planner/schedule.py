"""Backward scheduling from the event date, with compression."""

from dataclasses import dataclass
from datetime import date, timedelta

from planner.errors import PlanningError


@dataclass(frozen=True, slots=True)
class Schedule:
    """Maps "days before the event" to calendar dates.

    If there is less time than the ideal lead, every lead time is scaled down
    proportionally, so order is preserved and nothing is due in the past.
    """

    today: date
    event_date: date
    factor: float

    @classmethod
    def create(cls, today: date, event_date: date, max_lead: int) -> "Schedule":
        """Builds a schedule.

        Args:
            today: The planning date.
            event_date: The event date.
            max_lead: Longest ideal lead time in days.

        Returns:
            A schedule whose ``factor`` is below 1.0 if time is short.

        Raises:
            PlanningError: If the event date is in the past.
        """
        available = (event_date - today).days
        if available < 0:
            raise PlanningError("The event date is in the past.")
        factor = 1.0
        if max_lead > 0 and available < max_lead:
            factor = available / max_lead
        return cls(today, event_date, factor)

    @property
    def compressed(self) -> bool:
        """True when lead times had to be shortened."""
        return self.factor < 1.0

    @property
    def days_to_go(self) -> int:
        """Days from today to the event."""
        return (self.event_date - self.today).days

    def due(self, lead_days: int) -> date:
        """Returns the due date for a lead time (<= 0 means after the event)."""
        if lead_days <= 0:
            return self.event_date + timedelta(days=-lead_days)
        return self.event_date - timedelta(days=round(lead_days * self.factor))

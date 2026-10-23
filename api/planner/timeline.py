"""Timeline construction."""

from planner.catalog import MILESTONES, Milestone
from planner.models import EventRequest, TimelineItem
from planner.schedule import Schedule

URGENT_WITHIN_DAYS = 7


def applicable_milestones(request: EventRequest) -> list[Milestone]:
    """Milestones whose predicate holds for this request."""
    return [m for m in MILESTONES[request.event_type] if m.applies(request)]


def build_timeline(
    request: EventRequest, schedule: Schedule
) -> list[TimelineItem]:
    """Builds the dated milestone list, earliest first.

    Args:
        request: The validated request.
        schedule: Backward schedule for this event.

    Returns:
        Milestones sorted by due date (stable within a date).
    """
    items = [
        TimelineItem(
            key=m.key,
            label=m.label,
            due_date=due,
            days_until=(due - schedule.today).days,
            category=m.category,
            critical=m.critical,
            urgent=m.lead_days > 0
            and (due - schedule.today).days <= URGENT_WITHIN_DAYS,
        )
        for m in applicable_milestones(request)
        for due in [schedule.due(m.lead_days)]
    ]
    return sorted(items, key=lambda item: item.due_date)

"""Context-specific advisories."""

from planner.catalog import large_crowd, outdoor, young_child
from planner.models import Advisory, EventRequest, EventType, Tier
from planner.schedule import Schedule


def build_advisories(
    request: EventRequest, tier: Tier, schedule: Schedule
) -> list[Advisory]:
    """Returns warnings and tips derived from the request.

    Args:
        request: The validated request.
        tier: The budget tier.
        schedule: Backward schedule for this event.

    Returns:
        Advisories, most important first.
    """
    out: list[Advisory] = []
    if schedule.compressed:
        out.append(
            Advisory(
                level="warning",
                message=(
                    f"Only {schedule.days_to_go} days to go: lead times were "
                    "shortened. Book the items marked critical first."
                ),
            )
        )
    if tier is Tier.LEAN:
        out.append(
            Advisory(
                level="warning",
                message=(
                    "Budget per guest is tight. Food and venue are protected; "
                    "consider a smaller guest list or a simpler venue."
                ),
            )
        )
    if outdoor(request):
        out.append(
            Advisory(
                level="info",
                message="Outdoor setting: a weather backup is in the plan.",
            )
        )
    if young_child(request):
        out.append(
            Advisory(
                level="info",
                message="Plan one supervising adult for every few children.",
            )
        )
    if large_crowd(request) and request.event_type is not EventType.BIRTHDAY:
        out.append(
            Advisory(
                level="warning",
                message=(
                    "Large crowd: confirm the venue's licensed capacity, "
                    "fire exits and first-aid cover."
                ),
            )
        )
    return out

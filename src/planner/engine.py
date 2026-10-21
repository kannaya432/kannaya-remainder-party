"""Deterministic planning engine (pure, no I/O)."""

from datetime import date

from planner.advisories import build_advisories
from planner.budget import allocate_budget, classify_tier
from planner.models import EventRequest, Plan
from planner.schedule import Schedule
from planner.timeline import applicable_milestones, build_timeline
from planner.vendors import applicable_vendors, build_vendor_checklists


def build_plan(request: EventRequest, today: date) -> Plan:
    """Builds the full deterministic plan.

    Args:
        request: The validated request.
        today: The planning date (injected for testability).

    Returns:
        The plan.

    Raises:
        PlanningError: If the event date is in the past.
    """
    max_lead = max(
        [m.lead_days for m in applicable_milestones(request)]
        + [v.lead_days for v in applicable_vendors(request)]
    )
    schedule = Schedule.create(today, request.event_date, max_lead)
    tier = classify_tier(request)
    budget = allocate_budget(request, tier)
    return Plan(
        title=request.title,
        event_type=request.event_type,
        event_date=request.event_date,
        days_to_go=schedule.days_to_go,
        guest_count=request.guest_count,
        currency=request.currency,
        total_budget=request.budget,
        budget_per_guest=round(request.budget / request.guest_count),
        tier=tier,
        timeline_compressed=schedule.compressed,
        budget=budget,
        timeline=build_timeline(request, schedule),
        vendors=build_vendor_checklists(request, budget, schedule),
        advisories=build_advisories(request, tier, schedule),
    )

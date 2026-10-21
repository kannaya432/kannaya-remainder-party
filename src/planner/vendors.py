"""Vendor checklists."""

from collections import Counter
from collections.abc import Sequence

from planner.budget import split_evenly
from planner.catalog import VENDORS, VendorSpec
from planner.models import BudgetLine, EventRequest, VendorChecklist
from planner.schedule import Schedule


def applicable_vendors(request: EventRequest) -> list[VendorSpec]:
    """Vendor specs whose predicate holds for this request."""
    return [v for v in VENDORS[request.event_type] if v.applies(request)]


def _dietary_question(request: EventRequest) -> str:
    needs = ", ".join(d.value.replace("_", " ") for d in request.dietary)
    return f"Can you serve {needs} options with separate preparation?"


def build_vendor_checklists(
    request: EventRequest,
    budget: Sequence[BudgetLine],
    schedule: Schedule,
) -> list[VendorChecklist]:
    """Builds checklists, splitting each category budget among its vendors.

    Args:
        request: The validated request.
        budget: Allocated budget lines.
        schedule: Backward schedule for this event.

    Returns:
        Checklists sorted by book-by date.
    """
    specs = applicable_vendors(request)
    amounts = {line.key: line.amount for line in budget}
    counts = Counter(v.budget_category for v in specs)
    shares = {
        category: iter(split_evenly(amounts[category], n))
        for category, n in counts.items()
    }
    result = []
    for spec in specs:
        questions = list(spec.questions)
        if spec.dietary_sensitive and request.dietary:
            questions.insert(0, _dietary_question(request))
        result.append(
            VendorChecklist(
                key=spec.key,
                name=spec.name,
                estimated_budget=next(shares[spec.budget_category]),
                book_by=schedule.due(spec.lead_days),
                tasks=list(spec.tasks),
                questions=questions,
            )
        )
    return sorted(result, key=lambda v: v.book_by)

"""Context-aware budget allocation."""

from collections.abc import Sequence

from planner.catalog import (
    BUDGET_TEMPLATES,
    PER_GUEST_FLOOR,
    PRIORITY_TARGETS,
    outdoor,
)
from planner.models import BudgetLine, EventRequest, Tier

PRIORITY_BOOST = 1.25
DIETARY_BOOST = 1.06
OUTDOOR_BUFFER_BOOST = 1.25
LEAN_BELOW = 1.5  # x floor
PREMIUM_FROM = 6.0  # x floor


def classify_tier(request: EventRequest) -> Tier:
    """Classifies the budget per guest relative to a currency floor."""
    floor = PER_GUEST_FLOOR.get(request.currency)
    if floor is None:
        return Tier.STANDARD
    per_guest = request.budget / request.guest_count
    if per_guest < floor * LEAN_BELOW:
        return Tier.LEAN
    if per_guest >= floor * PREMIUM_FROM:
        return Tier.PREMIUM
    return Tier.STANDARD


def largest_remainder(total: int, weights: Sequence[float]) -> list[int]:
    """Splits an integer exactly in proportion to weights.

    Args:
        total: Non-negative integer to split.
        weights: Positive weights.

    Returns:
        Integer shares that sum to exactly ``total``.

    Raises:
        ValueError: If weights are empty or not all positive.
    """
    if not weights or any(w <= 0 for w in weights):
        raise ValueError("weights must be non-empty and positive")
    scale = sum(weights)
    raw = [total * w / scale for w in weights]
    shares = [int(x) for x in raw]
    leftover = total - sum(shares)
    by_fraction = sorted(
        range(len(raw)), key=lambda i: raw[i] - shares[i], reverse=True
    )
    for i in by_fraction[:leftover]:
        shares[i] += 1
    return shares


def split_evenly(total: int, parts: int) -> list[int]:
    """Splits ``total`` into ``parts`` near-equal integers."""
    return largest_remainder(total, [1.0] * parts)


def allocate_budget(request: EventRequest, tier: Tier) -> list[BudgetLine]:
    """Allocates the budget across categories using the host's context.

    Args:
        request: The validated request.
        tier: Result of :func:`classify_tier`.

    Returns:
        One line per category; amounts sum exactly to ``request.budget``.
    """
    categories = BUDGET_TEMPLATES[request.event_type]
    weights = {c.key: c.weight for c in categories}
    notes: dict[str, list[str]] = {c.key: [] for c in categories}
    targets = PRIORITY_TARGETS[request.event_type]

    for priority in request.priorities:
        key = targets[priority]
        weights[key] *= PRIORITY_BOOST
        label = priority.value.replace("_", " ")
        notes[key].append(f"Increased because you prioritised {label}.")
    if request.dietary:
        weights["catering"] *= DIETARY_BOOST
        notes["catering"].append("Extra allowance for special-diet sourcing.")
    if outdoor(request):
        weights["contingency"] *= OUTDOOR_BUFFER_BOOST
        notes["contingency"].append("Larger buffer for a weather backup.")
    for c in categories:
        if tier is Tier.LEAN and c.kind == "discretionary":
            weights[c.key] *= 0.8
            notes[c.key].append("Trimmed to protect food and venue.")
        elif tier is Tier.LEAN and c.kind == "core":
            weights[c.key] *= 1.1
        elif tier is Tier.PREMIUM and c.kind == "discretionary":
            weights[c.key] *= 1.1
            notes[c.key].append("Room for upgrades.")

    amounts = largest_remainder(
        request.budget, [weights[c.key] for c in categories]
    )
    return [
        BudgetLine(
            key=c.key,
            label=c.label,
            amount=amount,
            percent=round(amount * 100 / request.budget, 1),
            note=" ".join(notes[c.key]) or "Standard share for this event.",
        )
        for c, amount in zip(categories, amounts, strict=True)
    ]

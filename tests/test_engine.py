from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from helpers import TODAY, make
from planner.budget import (
    allocate_budget,
    classify_tier,
    largest_remainder,
    split_evenly,
)
from planner.engine import build_plan
from planner.errors import PlanningError
from planner.models import Tier
from planner.schedule import Schedule

requests = st.builds(
    lambda t, g, b, p, d, s, days: make(
        event_type=t,
        guest_count=g,
        budget=b,
        priorities=p,
        dietary=d,
        setting=s,
        event_date=(TODAY + timedelta(days=days)).isoformat(),
    ),
    st.sampled_from(["wedding", "birthday", "community"]),
    st.integers(1, 5000),
    st.integers(1, 1_000_000_000),
    st.lists(
        st.sampled_from(["food", "decor", "photography", "venue"]),
        max_size=3,
        unique=True,
    ),
    st.lists(st.sampled_from(["vegan", "jain", "halal"]), max_size=3),
    st.sampled_from(["indoor", "outdoor", "undecided"]),
    st.integers(0, 900),
)


@settings(max_examples=150, deadline=None)
@given(requests)
def test_plan_invariants(request) -> None:
    plan = build_plan(request, TODAY)
    # Budget always sums exactly and never goes negative.
    assert sum(b.amount for b in plan.budget) == request.budget
    assert all(b.amount >= 0 for b in plan.budget)
    # Vendor estimates never exceed what was budgeted.
    assert sum(v.estimated_budget for v in plan.vendors) <= request.budget
    # Pre-event milestones fall between today and the event, in order.
    dates = [t.due_date for t in plan.timeline]
    assert dates == sorted(dates)
    assert all(d >= TODAY for d in dates)
    assert all(
        v.book_by >= TODAY and v.book_by <= request.event_date
        for v in plan.vendors
    )
    assert plan.timeline[0].due_date >= TODAY


@given(
    st.integers(0, 10**9), st.lists(st.floats(0.1, 50), min_size=1, max_size=12)
)
def test_largest_remainder_exact(total: int, weights: list[float]) -> None:
    shares = largest_remainder(total, weights)
    assert sum(shares) == total and min(shares) >= 0


def test_largest_remainder_rejects_bad_weights() -> None:
    with pytest.raises(ValueError, match="positive"):
        largest_remainder(10, [1, 0])


def test_split_evenly() -> None:
    assert split_evenly(10, 3) == [4, 3, 3]


def test_priority_and_dietary_shift_budget() -> None:
    base = {b.key: b.amount for b in allocate_budget(make(), Tier.STANDARD)}
    boosted = {
        b.key: b.amount
        for b in allocate_budget(
            make(priorities=["decor"], dietary=["vegan"]), Tier.STANDARD
        )
    }
    assert boosted["decor"] > base["decor"]
    assert boosted["catering"] > base["catering"]


def test_outdoor_enlarges_contingency_and_adds_rentals() -> None:
    indoor = build_plan(make(setting="indoor"), TODAY)
    outdoor = build_plan(make(setting="outdoor"), TODAY)
    pick = lambda p: next(b.amount for b in p.budget if b.key == "contingency")  # noqa: E731
    assert pick(outdoor) > pick(indoor)
    assert "Tent, lighting & rentals" in [v.name for v in outdoor.vendors]
    assert "weather" in [t.key for t in outdoor.timeline]
    assert "weather" not in [t.key for t in indoor.timeline]


def test_tier_classification() -> None:
    assert classify_tier(make(budget=50_000, guest_count=200)) is Tier.LEAN
    assert (
        classify_tier(make(budget=2_000_000, guest_count=200)) is Tier.PREMIUM
    )
    assert classify_tier(make(budget=400_000, guest_count=200)) is Tier.STANDARD


def test_lean_budget_protects_core_and_warns() -> None:
    plan = build_plan(make(budget=50_000, guest_count=200), TODAY)
    assert plan.tier is Tier.LEAN
    assert any("tight" in a.message for a in plan.advisories)


def test_rush_event_is_compressed_and_flagged() -> None:
    plan = build_plan(
        make(event_date=(TODAY + timedelta(days=10)).isoformat()), TODAY
    )
    assert plan.timeline_compressed
    assert plan.advisories[0].level == "warning"
    assert any(t.urgent for t in plan.timeline)


def test_event_today_is_allowed_and_past_is_rejected() -> None:
    assert build_plan(make(event_date=TODAY.isoformat()), TODAY).days_to_go == 0
    with pytest.raises(PlanningError):
        build_plan(
            make(event_date=(TODAY - timedelta(days=1)).isoformat()), TODAY
        )


def test_dietary_question_added_for_caterer() -> None:
    plan = build_plan(make(dietary=["jain"]), TODAY)
    caterer = next(v for v in plan.vendors if v.key == "caterer")
    assert "jain" in caterer.questions[0]


def test_contextual_milestones() -> None:
    kid = build_plan(
        make(
            event_type="birthday", honoree_age=6, guest_count=20, budget=30_000
        ),
        TODAY,
    )
    adult = build_plan(
        make(
            event_type="birthday", honoree_age=30, guest_count=20, budget=30_000
        ),
        TODAY,
    )
    assert "supervision" in [t.key for t in kid.timeline]
    assert "supervision" not in [t.key for t in adult.timeline]
    crowd = build_plan(make(event_type="community", guest_count=400), TODAY)
    assert any("Large crowd" in a.message for a in crowd.advisories)


def test_schedule_post_event_item_not_compressed() -> None:
    s = Schedule.create(TODAY, TODAY + timedelta(days=5), 100)
    assert s.due(-7) == TODAY + timedelta(days=12)
    assert s.due(100) == TODAY
    assert s.due(0) == date(2026, 10, 25)

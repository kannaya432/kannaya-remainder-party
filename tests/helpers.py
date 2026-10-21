from datetime import date

from planner.models import EventRequest

TODAY = date(2026, 10, 20)


def make(**overrides: object) -> EventRequest:
    base: dict[str, object] = {
        "event_type": "wedding",
        "title": "Priya and Arjun",
        "event_date": "2027-10-20",
        "guest_count": 200,
        "budget": 2_000_000,
        "currency": "INR",
    }
    base.update(overrides)
    return EventRequest.model_validate(base)

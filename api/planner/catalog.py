"""Planning knowledge: budget splits, milestones and vendor checklists.

Everything here is plain data plus tiny predicates, so the planning rules can
be reviewed (and changed) without touching the engine.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from planner.models import Currency, EventRequest, EventType, Priority, Setting

Predicate = Callable[[EventRequest], bool]


def always(_: EventRequest) -> bool:
    """Applies to every request."""
    return True


def outdoor(r: EventRequest) -> bool:
    """Outdoor events need weather planning."""
    return r.setting is Setting.OUTDOOR


def has_guest_travel(r: EventRequest) -> bool:
    """Larger weddings usually involve out-of-town guests."""
    return r.guest_count >= 50


def young_child(r: EventRequest) -> bool:
    """Birthday child aged 12 or under."""
    return r.honoree_age is not None and r.honoree_age <= 12


def large_crowd(r: EventRequest) -> bool:
    """Crowds that need formal safety planning."""
    return r.guest_count >= 150


# --- Budget ---------------------------------------------------------------

Kind = Literal["core", "discretionary", "buffer"]


@dataclass(frozen=True, slots=True)
class BudgetCategory:
    """A budget bucket with its baseline weight (weights sum to 100)."""

    key: str
    label: str
    weight: float
    kind: Kind


BUDGET_TEMPLATES: Mapping[EventType, tuple[BudgetCategory, ...]] = {
    EventType.WEDDING: (
        BudgetCategory("venue", "Venue & rentals", 20, "core"),
        BudgetCategory("catering", "Food & beverage", 28, "core"),
        BudgetCategory("decor", "Decor & flowers", 10, "discretionary"),
        BudgetCategory("photo_video", "Photo & video", 10, "discretionary"),
        BudgetCategory("attire_beauty", "Attire & beauty", 9, "discretionary"),
        BudgetCategory(
            "entertainment", "Music & entertainment", 6, "discretionary"
        ),
        BudgetCategory("invitations", "Invitations & stationery", 2, "core"),
        BudgetCategory("guest_experience", "Guest travel & stay", 5, "core"),
        BudgetCategory("rituals", "Officiant & rituals", 2, "core"),
        BudgetCategory("contingency", "Contingency", 8, "buffer"),
    ),
    EventType.BIRTHDAY: (
        BudgetCategory("venue", "Venue or home setup", 15, "core"),
        BudgetCategory("catering", "Food & cake", 35, "core"),
        BudgetCategory("decor", "Decor & balloons", 12, "discretionary"),
        BudgetCategory(
            "entertainment", "Entertainment & games", 15, "discretionary"
        ),
        BudgetCategory("photo_video", "Photography", 5, "discretionary"),
        BudgetCategory("guest_experience", "Party favours", 6, "core"),
        BudgetCategory("invitations", "Invitations", 2, "core"),
        BudgetCategory("contingency", "Contingency", 10, "buffer"),
    ),
    EventType.COMMUNITY: (
        BudgetCategory("venue", "Venue & permissions", 18, "core"),
        BudgetCategory("catering", "Food & refreshments", 28, "core"),
        BudgetCategory("av_tech", "Sound, stage & power", 12, "core"),
        BudgetCategory("decor", "Decor & signage", 8, "discretionary"),
        BudgetCategory(
            "entertainment", "Programme & entertainment", 12, "discretionary"
        ),
        BudgetCategory("safety", "Safety & first aid", 5, "core"),
        BudgetCategory("publicity", "Publicity", 5, "discretionary"),
        BudgetCategory("guest_experience", "Volunteers & logistics", 4, "core"),
        BudgetCategory("contingency", "Contingency", 8, "buffer"),
    ),
}

# Which budget category each user priority boosts, per event type.
PRIORITY_TARGETS: Mapping[EventType, Mapping[Priority, str]] = {
    event_type: {
        Priority.FOOD: "catering",
        Priority.DECOR: "decor",
        Priority.PHOTOGRAPHY: "photo_video"
        if event_type is not EventType.COMMUNITY
        else "publicity",
        Priority.ENTERTAINMENT: "entertainment",
        Priority.VENUE: "venue",
        Priority.GUEST_EXPERIENCE: "guest_experience",
    }
    for event_type in EventType
}

# Rough minimum sensible spend per guest. Used only to classify the tier;
# see "Assumptions" in the README.
PER_GUEST_FLOOR: Mapping[Currency, int] = {
    Currency.INR: 400,
    Currency.USD: 10,
    Currency.EUR: 10,
    Currency.GBP: 9,
    Currency.AUD: 15,
    Currency.CAD: 13,
    Currency.SGD: 14,
    Currency.AED: 40,
}

# --- Milestones -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Milestone:
    """A task due ``lead_days`` before the event (<= 0 means after)."""

    key: str
    label: str
    lead_days: int
    category: str
    critical: bool = False
    applies: Predicate = always


MILESTONES: Mapping[EventType, tuple[Milestone, ...]] = {
    EventType.WEDDING: (
        Milestone(
            "budget",
            "Agree budget, guest-list draft and priorities",
            360,
            "planning",
        ),
        Milestone("venue", "Book venue and lock the date", 330, "venue", True),
        Milestone(
            "photo",
            "Book photographer and videographer",
            300,
            "photo_video",
            True,
        ),
        Milestone(
            "caterer",
            "Book caterer and schedule a tasting",
            240,
            "catering",
            True,
        ),
        Milestone(
            "legal", "Start marriage registration paperwork", 210, "legal", True
        ),
        Milestone("save_date", "Send save-the-dates", 180, "invitations"),
        Milestone(
            "attire",
            "Choose attire and book beauty trials",
            180,
            "attire_beauty",
        ),
        Milestone(
            "decor", "Book decor, florist and entertainment", 150, "decor"
        ),
        Milestone(
            "travel",
            "Arrange guest travel and stay",
            120,
            "guest_experience",
            False,
            has_guest_travel,
        ),
        Milestone(
            "invites", "Send formal invitations", 56, "invitations", True
        ),
        Milestone(
            "rsvp", "Chase RSVPs and fix final headcount", 28, "planning"
        ),
        Milestone(
            "menu",
            "Finalise menu, seating plan and run of show",
            21,
            "catering",
        ),
        Milestone(
            "vendors",
            "Reconfirm every vendor and payment schedule",
            14,
            "planning",
            True,
        ),
        Milestone(
            "fittings", "Final fittings and beauty trials", 14, "attire_beauty"
        ),
        Milestone(
            "weather",
            "Confirm weather backup for the outdoor setup",
            14,
            "venue",
            True,
            outdoor,
        ),
        Milestone(
            "rehearsal",
            "Hold rehearsal and share the day-of schedule",
            3,
            "planning",
        ),
        Milestone(
            "balances",
            "Pay final balances and prepare tip envelopes",
            2,
            "planning",
        ),
        Milestone("event", "Wedding day", 0, "event", True),
        Milestone(
            "thanks",
            "Send thank-you notes and settle final invoices",
            -7,
            "planning",
        ),
    ),
    EventType.BIRTHDAY: (
        Milestone(
            "plan", "Pick the date, guest list and budget", 56, "planning"
        ),
        Milestone(
            "venue",
            "Book the venue (or plan the home layout)",
            49,
            "venue",
            True,
        ),
        Milestone(
            "entertainment",
            "Book entertainer or plan activities",
            35,
            "entertainment",
        ),
        Milestone(
            "menu", "Choose menu and check dietary needs", 28, "catering"
        ),
        Milestone("cake", "Order the cake", 21, "catering", True),
        Milestone("invites", "Send invitations", 21, "invitations", True),
        Milestone(
            "supervision",
            "Plan kid-safe activities and adult supervision",
            14,
            "guest_experience",
            False,
            young_child,
        ),
        Milestone("supplies", "Buy decor and party favours", 14, "decor"),
        Milestone(
            "weather",
            "Confirm weather backup for the outdoor setup",
            10,
            "venue",
            True,
            outdoor,
        ),
        Milestone("rsvp", "Confirm RSVPs", 7, "planning"),
        Milestone(
            "vendors",
            "Reconfirm vendors and delivery times",
            5,
            "planning",
            True,
        ),
        Milestone(
            "prep", "Shop for perishables and prepare the venue", 2, "planning"
        ),
        Milestone("event", "Birthday celebration", 0, "event", True),
    ),
    EventType.COMMUNITY: (
        Milestone(
            "committee", "Set the goal, committee and roles", 120, "planning"
        ),
        Milestone(
            "venue", "Secure venue and local permissions", 105, "venue", True
        ),
        Milestone(
            "volunteers",
            "Recruit volunteers and assign roles",
            90,
            "guest_experience",
        ),
        Milestone(
            "funding", "Reach out to sponsors and donors", 90, "planning"
        ),
        Milestone(
            "av", "Book sound, stage and power backup", 60, "av_tech", True
        ),
        Milestone("food", "Book caterer or food stalls", 45, "catering", True),
        Milestone(
            "publicity",
            "Launch publicity (posters, social, groups)",
            42,
            "publicity",
        ),
        Milestone(
            "safety",
            "Write the safety plan: first aid, exits, crowd flow",
            30,
            "safety",
            True,
        ),
        Milestone(
            "programme",
            "Finalise the programme and run of show",
            21,
            "entertainment",
        ),
        Milestone(
            "weather",
            "Confirm weather backup for the outdoor setup",
            14,
            "venue",
            True,
            outdoor,
        ),
        Milestone(
            "briefing",
            "Brief volunteers and walk the venue",
            7,
            "guest_experience",
        ),
        Milestone("vendors", "Reconfirm every vendor", 7, "planning", True),
        Milestone("setup", "Set up and run a sound check", 1, "av_tech"),
        Milestone("event", "Event day", 0, "event", True),
        Milestone(
            "thanks",
            "Thank volunteers and publish a short report",
            -5,
            "planning",
        ),
    ),
}

# --- Vendors --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VendorSpec:
    """A vendor category with a reusable checklist."""

    key: str
    name: str
    budget_category: str
    lead_days: int
    tasks: tuple[str, ...]
    questions: tuple[str, ...]
    dietary_sensitive: bool = False
    applies: Predicate = always


_PAY = "What is the payment schedule and cancellation policy?"
_BACKUP = "What is your backup plan if something goes wrong on the day?"

_RENTALS = VendorSpec(
    "rentals",
    "Tent, lighting & rentals",
    "venue",
    60,
    ("Get quotes for tent or canopy cover", "Plan power and lighting"),
    ("Is wind and rain cover included?", "Who sets up and who removes?"),
    applies=outdoor,
)

VENDORS: Mapping[EventType, tuple[VendorSpec, ...]] = {
    EventType.WEDDING: (
        VendorSpec(
            "venue",
            "Venue",
            "venue",
            330,
            (
                "Visit two or three shortlisted venues",
                "Confirm capacity, parking and noise limits",
                "Ask about in-house vendor rules",
            ),
            (
                "What is the exact guest capacity?",
                "Until what time can we use the space?",
                _PAY,
            ),
        ),
        _RENTALS,
        VendorSpec(
            "caterer",
            "Caterer",
            "catering",
            240,
            (
                "Shortlist caterers and attend a tasting",
                "Fix per-plate price and serving staff count",
            ),
            (
                "What is included per plate?",
                "How much food is prepared as a buffer?",
                _PAY,
            ),
            dietary_sensitive=True,
        ),
        VendorSpec(
            "photo",
            "Photographer & videographer",
            "photo_video",
            300,
            (
                "Review full wedding albums, not only highlights",
                "List must-have shots and family groups",
            ),
            (
                "How many photographers will attend?",
                "When will we receive edited files?",
                _BACKUP,
            ),
        ),
        VendorSpec(
            "decor",
            "Decor & florist",
            "decor",
            150,
            (
                "Share a mood board and colour palette",
                "Confirm set-up and tear-down times",
            ),
            ("Which flowers are in season for our date?", _BACKUP, _PAY),
        ),
        VendorSpec(
            "music",
            "Music, DJ or band",
            "entertainment",
            150,
            (
                "Share a must-play and do-not-play list",
                "Check sound limits at the venue",
            ),
            ("What equipment do you bring?", _BACKUP, _PAY),
        ),
        VendorSpec(
            "attire",
            "Attire & beauty",
            "attire_beauty",
            180,
            ("Book fittings and trials", "Plan alterations time"),
            ("How long do alterations take?", _PAY),
        ),
        VendorSpec(
            "stationery",
            "Invitations & stationery",
            "invitations",
            90,
            ("Finalise wording and languages", "Proof every name and date"),
            (
                "What is the print turnaround?",
                "Can you send a digital version too?",
            ),
        ),
        VendorSpec(
            "transport",
            "Guest travel & stay",
            "guest_experience",
            120,
            (
                "Block hotel rooms or homestays",
                "Arrange local transport and signage",
            ),
            ("What is the room-block release date?", _PAY),
            applies=has_guest_travel,
        ),
        VendorSpec(
            "officiant",
            "Officiant & rituals",
            "rituals",
            210,
            (
                "Confirm the ceremony order and duration",
                "Prepare the list of ritual items",
            ),
            (
                "Which items should the family arrange?",
                "How long will the ceremony take?",
            ),
        ),
    ),
    EventType.BIRTHDAY: (
        VendorSpec(
            "venue",
            "Venue or home setup",
            "venue",
            49,
            (
                "Confirm capacity and booking hours",
                "Plan seating, parking and washrooms",
            ),
            ("Is a security deposit needed?", _PAY),
        ),
        _RENTALS,
        VendorSpec(
            "caterer",
            "Caterer & cake",
            "catering",
            28,
            (
                "Choose menu and confirm headcount",
                "Order cake with a flavour that suits the dietary needs",
            ),
            (
                "Can you label allergens clearly?",
                "What is the delivery window?",
                _PAY,
            ),
            dietary_sensitive=True,
        ),
        VendorSpec(
            "decor",
            "Decor & balloons",
            "decor",
            14,
            ("Pick a theme and colour palette", "Confirm set-up time"),
            ("What is the set-up time needed?", _PAY),
        ),
        VendorSpec(
            "entertainer",
            "Entertainer or games host",
            "entertainment",
            35,
            (
                "Match activities to the age group",
                "Prepare a rain-or-shine plan",
            ),
            ("How long is the programme?", _BACKUP, _PAY),
        ),
        VendorSpec(
            "photo",
            "Photographer",
            "photo_video",
            21,
            ("Share a list of moments to capture",),
            ("How soon will photos be delivered?", _PAY),
        ),
        VendorSpec(
            "favours",
            "Party favours",
            "guest_experience",
            14,
            (
                "Pick safe, age-appropriate favours",
                "Order one extra per ten guests",
            ),
            ("What is the delivery date?",),
        ),
        VendorSpec(
            "stationery",
            "Invitations",
            "invitations",
            21,
            ("Include date, time, address and RSVP date",),
            ("Can you share a digital invite?",),
        ),
    ),
    EventType.COMMUNITY: (
        VendorSpec(
            "venue",
            "Venue & permissions",
            "venue",
            105,
            (
                "Obtain written permission from the owner or authority",
                "Confirm power, water and washrooms",
            ),
            (
                "Which permits are required?",
                "What are the closing time and noise limits?",
                _PAY,
            ),
        ),
        _RENTALS,
        VendorSpec(
            "caterer",
            "Caterer or food stalls",
            "catering",
            45,
            ("Confirm food-safety licence", "Plan queues and waste bins"),
            (
                "What is the per-head cost?",
                "How do you handle surplus food?",
                _PAY,
            ),
            dietary_sensitive=True,
        ),
        VendorSpec(
            "av",
            "Sound, stage & power",
            "av_tech",
            60,
            (
                "Do a site visit for stage and speaker placement",
                "Arrange a generator or power backup",
            ),
            ("What is the total power load?", _BACKUP, _PAY),
        ),
        VendorSpec(
            "decor",
            "Decor & signage",
            "decor",
            30,
            (
                "Plan clear directional signs",
                "Include accessible-route signage",
            ),
            ("What is the print turnaround?", _PAY),
        ),
        VendorSpec(
            "programme",
            "Programme & performers",
            "entertainment",
            30,
            ("Build a timed run of show", "Confirm performer needs"),
            ("What is your technical requirement?", _PAY),
        ),
        VendorSpec(
            "safety",
            "Safety & first aid",
            "safety",
            30,
            ("Arrange a first-aid desk", "Mark fire exits and assign marshals"),
            ("Is a trained medic available?", "Where is the nearest hospital?"),
            applies=always,
        ),
        VendorSpec(
            "publicity",
            "Publicity & printing",
            "publicity",
            42,
            ("Design a one-page poster", "Share in community groups"),
            ("What is the print turnaround?",),
        ),
        VendorSpec(
            "volunteers",
            "Volunteers & logistics",
            "guest_experience",
            90,
            (
                "Assign leads for registration, food, safety",
                "Prepare a volunteer briefing sheet",
            ),
            ("Who is the single point of contact on the day?",),
        ),
    ),
}

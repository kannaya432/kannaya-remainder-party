"""Typed request and response models (validated at the trust boundary)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from planner.sanitize import clean_text


class EventType(StrEnum):
    """Supported event verticals."""

    WEDDING = "wedding"
    BIRTHDAY = "birthday"
    COMMUNITY = "community"


class Currency(StrEnum):
    """Supported ISO-4217 currencies."""

    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AUD = "AUD"
    CAD = "CAD"
    SGD = "SGD"
    AED = "AED"


class Dietary(StrEnum):
    """Dietary requirements the caterer must cover."""

    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    JAIN = "jain"
    HALAL = "halal"
    GLUTEN_FREE = "gluten_free"
    NUT_FREE = "nut_free"


class Priority(StrEnum):
    """What the host most wants to invest in."""

    FOOD = "food"
    DECOR = "decor"
    PHOTOGRAPHY = "photography"
    ENTERTAINMENT = "entertainment"
    VENUE = "venue"
    GUEST_EXPERIENCE = "guest_experience"


class Setting(StrEnum):
    """Indoor / outdoor preference."""

    UNDECIDED = "undecided"
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class Tier(StrEnum):
    """Budget-per-guest classification that drives allocation."""

    LEAN = "lean"
    STANDARD = "standard"
    PREMIUM = "premium"


def _dedupe[T](items: list[T]) -> list[T]:
    return list(dict.fromkeys(items))


class EventRequest(BaseModel):
    """What the user wants to plan. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: EventType
    title: str = Field(min_length=1, max_length=80)
    event_date: date
    guest_count: int = Field(ge=1, le=5000)
    budget: int = Field(ge=1, le=1_000_000_000)
    currency: Currency = Currency.INR
    city: str | None = Field(default=None, max_length=60)
    cultural_style: str | None = Field(default=None, max_length=60)
    theme_preferences: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    dietary: list[Dietary] = Field(default_factory=list, max_length=6)
    priorities: list[Priority] = Field(default_factory=list, max_length=3)
    setting: Setting = Setting.UNDECIDED
    honoree_age: int | None = Field(default=None, ge=0, le=120)

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, value: object) -> object:
        return clean_text(value) if isinstance(value, str) else value

    @field_validator(
        "city", "cultural_style", "theme_preferences", "notes", mode="before"
    )
    @classmethod
    def _clean_optional(cls, value: object) -> object:
        if isinstance(value, str):
            return clean_text(value) or None
        return value

    @field_validator("dietary", "priorities", mode="after")
    @classmethod
    def _unique(cls, value: list[Dietary] | list[Priority]) -> list[object]:
        return _dedupe(list(value))

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.honoree_age is not None and self.event_type != (
            EventType.BIRTHDAY
        ):
            raise ValueError("honoree_age applies to birthdays only")
        return self


class BudgetLine(BaseModel):
    """One budget category with its allocation and reasoning."""

    key: str
    label: str
    amount: int
    percent: float
    note: str


class TimelineItem(BaseModel):
    """A dated milestone."""

    key: str
    label: str
    due_date: date
    days_until: int
    category: str
    critical: bool
    urgent: bool


class VendorChecklist(BaseModel):
    """Checklist for one vendor category."""

    key: str
    name: str
    estimated_budget: int
    book_by: date
    tasks: list[str]
    questions: list[str]


class Advisory(BaseModel):
    """A context-specific heads-up."""

    level: Literal["info", "warning"]
    message: str


class Plan(BaseModel):
    """The deterministic part of the plan."""

    title: str
    event_type: EventType
    event_date: date
    days_to_go: int
    guest_count: int
    currency: Currency
    total_budget: int
    budget_per_guest: int
    tier: Tier
    timeline_compressed: bool
    budget: list[BudgetLine]
    timeline: list[TimelineItem]
    vendors: list[VendorChecklist]
    advisories: list[Advisory]


class Theme(BaseModel):
    """A theme suggestion."""

    name: str = Field(max_length=60)
    description: str = Field(max_length=240)


class IdeaSet(BaseModel):
    """Personalised ideas (from Gemini or the curated fallback)."""

    themes: list[Theme] = Field(min_length=1, max_length=4)
    activities: list[str] = Field(max_length=6)
    menu: list[str] = Field(max_length=6)
    personal_touches: list[str] = Field(max_length=5)
    savings_tips: list[str] = Field(max_length=4)


class IdeasResponse(BaseModel):
    """Response of the ideas endpoint (kept separate so the plan is instant)."""

    ideas: IdeaSet
    ideas_source: Literal["gemini", "curated"]
    generated_at: datetime

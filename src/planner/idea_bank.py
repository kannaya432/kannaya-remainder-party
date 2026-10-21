"""Curated, deterministic ideas used when Gemini is unavailable."""

import hashlib
from collections.abc import Sequence

from planner.models import (
    Dietary,
    EventRequest,
    EventType,
    IdeaSet,
    Theme,
    Tier,
)

_THEMES: dict[EventType, tuple[Theme, ...]] = {
    EventType.WEDDING: (
        Theme(
            name="Marigold & mango leaves",
            description="Warm yellows and fresh greens with traditional garlands and brass lamps.",
        ),
        Theme(
            name="Garden twilight",
            description="Soft lanterns, pastel florals and an evening ceremony outdoors.",
        ),
        Theme(
            name="Heritage minimal",
            description="Handloom textures, clay diyas and a calm ivory-and-gold palette.",
        ),
        Theme(
            name="Jewel tones",
            description="Deep emerald, ruby and sapphire accents with layered lighting.",
        ),
        Theme(
            name="Beachside breeze",
            description="Light fabrics, shells and sunset colours for a relaxed feel.",
        ),
    ),
    EventType.BIRTHDAY: (
        Theme(
            name="Adventure explorers",
            description="Treasure maps, scavenger hunts and earthy colours.",
        ),
        Theme(
            name="Pastel carnival",
            description="Soft colours, popcorn stand and simple carnival games.",
        ),
        Theme(
            name="Space party",
            description="Glow stars, planet balloons and a mission-themed cake.",
        ),
        Theme(
            name="Retro game night",
            description="Board games, arcade-style decor and a trophy table.",
        ),
        Theme(
            name="Garden picnic",
            description="Floor cushions, bunting and homemade treats outdoors.",
        ),
    ),
    EventType.COMMUNITY: (
        Theme(
            name="Festival of lights",
            description="Lamps, rangoli and a shared evening programme.",
        ),
        Theme(
            name="Neighbourhood fair",
            description="Food stalls, a kids' corner and local talent on stage.",
        ),
        Theme(
            name="Heritage evening",
            description="Folk performances and a small photo exhibition.",
        ),
        Theme(
            name="Green day",
            description="Plant swap, recycled-craft stalls and a cleanup drive.",
        ),
        Theme(
            name="Open-air cinema",
            description="Mats, a projector screen and community-voted films.",
        ),
    ),
}

_ACTIVITIES: dict[EventType, tuple[str, ...]] = {
    EventType.WEDDING: (
        "Welcome drinks with a live instrumental trio",
        "A memory wall where guests pin favourite photos",
        "Mehendi or henna corner for guests",
        "A family-stories slideshow before dinner",
        "A photo booth with handmade props",
        "A short toast round from friends and elders",
        "Sunset couple portraits before the reception",
    ),
    EventType.BIRTHDAY: (
        "Treasure hunt across the venue",
        "DIY craft table matched to the theme",
        "Musical chairs and freeze-dance rounds",
        "Photo wall with props",
        "Cake-cutting with a short video of wishes",
        "Quiet corner with books and puzzles",
    ),
    EventType.COMMUNITY: (
        "Welcome desk with name tags and a map",
        "Kids' corner with supervised games",
        "Open-mic slot for local performers",
        "Community photo wall",
        "Raffle supporting a local cause",
        "Volunteer recognition moment on stage",
    ),
}

_MENU: dict[EventType, tuple[str, ...]] = {
    EventType.WEDDING: (
        "Live chaat and dosa counters",
        "Regional thali with two seasonal vegetables",
        "Fresh fruit and sherbet station",
        "A dessert table with two traditional sweets",
        "Hot filter coffee and tea counter",
    ),
    EventType.BIRTHDAY: (
        "Mini sliders or sandwiches and a veggie platter",
        "Build-your-own pizza or wrap station",
        "Fresh juices and a fruit bar",
        "A cake with a simple eggless option",
        "Popcorn and snack cups for kids",
    ),
    EventType.COMMUNITY: (
        "Simple one-plate meal that is quick to serve",
        "Tea, coffee and a snack stall",
        "Seasonal fruit and water points",
        "A regional sweet to share",
    ),
}

_DIETARY_MENU: dict[Dietary, str] = {
    Dietary.VEGETARIAN: "Keep the whole menu vegetarian so nobody is singled out",
    Dietary.VEGAN: "Add a clearly labelled vegan main and dessert",
    Dietary.JAIN: "Prepare a separate Jain counter with no root vegetables",
    Dietary.HALAL: "Use certified halal suppliers and keep prep areas separate",
    Dietary.GLUTEN_FREE: "Offer a gluten-free main and dessert, labelled",
    Dietary.NUT_FREE: "Keep all dishes nut-free and label every allergen",
}

_TOUCHES = (
    "Handwritten notes from guests in a keepsake box",
    "A playlist built from guests' song requests",
    "A short welcome message that tells the story behind the day",
    "Small favours that reflect your hometown",
    "A reserved seat with a framed photo for someone who cannot attend",
)

_SAVINGS = (
    "Choose a weekday or off-season date for better venue rates",
    "Compare at least three quotes for each major vendor",
    "Use seasonal flowers and reuse ceremony decor at the reception",
    "Print fewer invitations and send digital ones to close family",
    "Ask friends with a skill (music, photography) for a small paid role",
)


def _pick[T](items: Sequence[T], seed: str, count: int) -> list[T]:
    """Deterministic selection: rank by hash(seed + index), keep ``count``."""
    ranked = sorted(
        range(len(items)),
        key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).digest(),
    )
    return [items[i] for i in ranked[:count]]


def curated_ideas(request: EventRequest, tier: Tier) -> IdeaSet:
    """Builds deterministic ideas from the host's context.

    Args:
        request: The validated request.
        tier: The budget tier (lean events get more savings tips).

    Returns:
        A small, relevant set of ideas. The same request always yields the
        same ideas.
    """
    seed = request.model_dump_json()
    menu = [_DIETARY_MENU[d] for d in request.dietary]
    menu += _pick(_MENU[request.event_type], seed + "m", 5 - min(len(menu), 3))
    touches = _pick(_TOUCHES, seed + "t", 3)
    if request.cultural_style:
        touches.insert(
            0,
            f"Weave {request.cultural_style} traditions into the programme "
            "and ask elders to guide the details",
        )
    return IdeaSet(
        themes=_pick(_THEMES[request.event_type], seed + "h", 3),
        activities=_pick(_ACTIVITIES[request.event_type], seed + "a", 4),
        menu=menu[:6],
        personal_touches=touches[:5],
        savings_tips=_pick(_SAVINGS, seed + "s", 4 if tier is Tier.LEAN else 2),
    )

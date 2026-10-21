"""iCalendar (RFC 5545) export of the timeline."""

import hashlib
from datetime import datetime, timedelta

from planner.models import Plan

_CRLF = "\r\n"


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Folds a line to 75 octets without splitting a UTF-8 character."""
    data = line.encode()
    if len(data) <= 75:
        return line
    parts: list[str] = []
    current = ""
    limit = 75
    for ch in line:
        if len((current + ch).encode()) > limit:
            parts.append(current)
            current, limit = ch, 74  # continuation lines start with a space
        else:
            current += ch
    parts.append(current)
    return (_CRLF + " ").join(parts)


def build_ics(plan: Plan, now: datetime) -> str:
    """Renders the plan's timeline as an all-day-event calendar.

    Args:
        plan: The plan.
        now: Timestamp for DTSTAMP (UTC).

    Returns:
        The calendar text with CRLF line endings.
    """
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Celebration Planner//EN",
        "CALSCALE:GREGORIAN",
    ]
    for item in plan.timeline:
        uid = hashlib.sha256(
            f"{plan.title}|{plan.event_date}|{item.key}".encode()
        ).hexdigest()[:24]
        end = item.due_date + timedelta(days=1)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@celebration-planner",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{item.due_date:%Y%m%d}",
            f"DTEND;VALUE=DATE:{end:%Y%m%d}",
            f"SUMMARY:{_escape(f'{plan.title}: {item.label}')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return _CRLF.join(_fold(line) for line in lines) + _CRLF

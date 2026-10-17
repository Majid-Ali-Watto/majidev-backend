"""Keeps experience durations in the published README (and bio) current, the way the site computes them.

/admin wraps every duration it writes in a marker carrying the job dates it came from: `experience` for a total
(getTotalExperince) and `duration` for one job (getExperienceYear), as the site shows them:

    <!--experience:2025-09-15~Present,2022-10-24~2025-04-25-->**3Y 11M**<!--/experience-->
    <!--duration:2025-09-15~Present-->1Y 1M<!--/duration-->

and, when the bio uses "Y-M-D", adds a hidden comment with the bio template and the job dates:

    <!--github-bio:{"template": "... Y-M-D ...", "experience": [["2025-09-15", "Present"], ...]}-->

so a refresh needs nothing but the README itself.
"""

import json
import re
from datetime import date, timedelta

MARKER = re.compile(r"(<!--(experience|duration):([^>]*?)-->)(.*?)(<!--/\2-->)", re.S)
BIO_STATE = re.compile(r"<!--github-bio:(.*?)-->", re.S)
DURATION = re.compile(r"\d+Y \d+M")
PLACEHOLDER = "Y-M-D"


def _end(value: str, today: date) -> date:
    return today if value == "Present" else date.fromisoformat(value)


def span(start: str, end: str, today: date) -> tuple[int, int, int]:
    """Years, months and days between two dates; matches getExperienceYear in src/utils/getExpYears.js."""
    first, last = date.fromisoformat(start), _end(end, today)
    years, months, days = last.year - first.year, last.month - first.month, last.day - first.day
    if days < 0:
        months -= 1
        days += (last.replace(day=1) - timedelta(days=1)).day  # length of the month before `last`
    if months < 0:
        years -= 1
        months += 12
    return years, months, days


def duration(start: str, end: str, today: date) -> str:
    """One job's length as "1Y 1M"; matches getExperienceYear's text in src/utils/getExpYears.js."""
    years, months, _ = span(start, end, today)
    return f"{years}Y {months}M"


def total(ranges: list[tuple[str, str]], today: date) -> str:
    """Summed experience as "3Y 11M"; matches getTotalExperince in src/utils/getExpYears.js."""
    years = months = days = 0
    for start, end in ranges:
        y, m, d = span(start, end, today)
        years, months, days = years + y, months + m, days + d
    # Carry over only from full units, like the site (a job's day count can be negative, e.g. Jan 31 → Mar 1)
    if days >= 30:
        months += days // 30
    if months >= 12:
        years, months = years + months // 12, months % 12
    return f"{years}Y {months}M"


def _ranges(spec: str) -> list[tuple[str, str]]:
    return [tuple(part.split("~", 1)) for part in spec.split(",") if "~" in part]


def refresh_readme(markdown: str, today: date) -> str:
    """The README with every marked duration recomputed for `today`."""

    def update(match: re.Match) -> str:
        opening, kind, spec, inner, closing = match.groups()
        ranges = _ranges(spec)
        value = total(ranges, today) if kind == "experience" else duration(*ranges[0], today)
        return opening + DURATION.sub(value, inner, count=1) + closing

    return MARKER.sub(update, markdown)


def bio_from_readme(markdown: str, today: date) -> str | None:
    """The bio for `today`, if the README carries a bio template; None otherwise."""
    match = BIO_STATE.search(markdown)
    if not match:
        return None
    state = json.loads(match.group(1))
    return state["template"].replace(PLACEHOLDER, total([tuple(r) for r in state["experience"]], today))

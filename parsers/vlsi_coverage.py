"""Shared helpers for the VLSI conference parsers.

This module owns three things that several parsers need:

* loading the canonical target venue list from ``all_vlsi_conf_names.csv``
* matching a source-provided conference name to one of those targets
  (case-insensitive, tolerant of trailing years and punctuation)
* parsing the messy human date ranges the sources hand us
* a coverage report used by the integration layer to warn about targets
  that currently have no upcoming entry

Keeping this logic in one place means ccf_deadlines, wikicfp and ieee_cas
all normalise names and dates identically.
"""

import csv
import os
import re
from datetime import date, datetime

# all_vlsi_conf_names.csv lives at the repository root, one level up from parsers/
_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "all_vlsi_conf_names.csv")

# Venues that are not literally in the CSV but are close enough to be worth
# surfacing (architecture / EDA / test venues). Stored as normalised keys.
_RELATED = {
    "hpca",
    "hotchips",
    "emsoft",
    "codesisss",
    "codes",
    "ispass",
    "fmcad",
    "rtas",
    "fpt",
    "fccm",
    "ets",
    "ats",
    "itc",
}

# Normalised source name -> canonical CSV short name, for cases where the
# source uses a different acronym than the CSV.
_ALIASES = {
    "dsd": "Euromicro DSD",
    "esserc": "ESSCIRC",          # ESSCIRC+ESSDERC merged into "ESSERC"
    "vlsicircuits": "Symp VLSI Circuits",
    "vlsisymposium": "Symp VLSI Circuits",
    "symposiumonvlsi": "Symp VLSI Circuits",
    "asilomar": "Asilomar Conf",
}


def normalize(name):
    """Lowercase, drop any standalone 4-digit year, and strip punctuation.

    "ISLPED 2026" -> "islped", "ASP-DAC" -> "aspdac".
    """
    if not name:
        return ""
    lowered = name.lower()
    lowered = re.sub(r"\b(19|20)\d{2}\b", " ", lowered)  # drop years like 2026
    return re.sub(r"[^a-z0-9]", "", lowered)


def load_targets():
    """Return the list of target venues as dicts with ``short`` and ``full``."""
    targets = []
    with open(_CSV_PATH, newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            short = row[0].strip()
            if not short or short.lower() == "name":
                continue
            full = row[1].strip() if len(row) > 1 else ""
            targets.append({"short": short, "full": full})
    return targets


# Build the normalised-short -> canonical-short lookup once at import time.
_SHORT_BY_NORM = {normalize(t["short"]): t["short"] for t in load_targets()}


def canonical_target(name):
    """Map a source name to its CSV short name, or None if it is not a target."""
    norm = normalize(name)
    if not norm:
        return None
    if norm in _SHORT_BY_NORM:
        return _SHORT_BY_NORM[norm]
    if norm in _ALIASES:
        return _ALIASES[norm]
    return None


def is_relevant(name):
    """True if the name is a CSV target or a closely-related VLSI venue."""
    return canonical_target(name) is not None or normalize(name) in _RELATED


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MON = r"([A-Za-z]{3,9})"


def _month_num(token):
    return _MONTHS.get(token[:3].lower())


def _iso(year, month, day):
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_date_range(text):
    """Parse a human conference date range into ``(start_iso, end_iso)``.

    Handles the formats seen across our sources, e.g.::

        "July 26-29, 2026"            (same month)
        "October 27 - 31, 2024"       (same month, spaced)
        "Oct 29 - Nov 2, 2023"        (cross month)
        "Jul 26, 2026 - Jul 29, 2026" (WikiCFP, full both sides)
        "28 Jul 2026 - 30 Jul 2026"   (IEEE CAS, day first)

    Returns ``(None, None)`` when nothing parseable is found.
    """
    if not text:
        return None, None
    # Normalise dashes and drop periods after abbreviated months ("Sep. 14").
    t = text.replace("–", "-").replace("—", "-").replace(".", " ").strip()

    # "Jul 26, 2026 - Jul 29, 2026" — month first, year on both sides
    m = re.search(
        _MON + r"\s+(\d{1,2}),?\s*(\d{4})\s*-\s*" + _MON + r"\s+(\d{1,2}),?\s*(\d{4})", t
    )
    if m and _month_num(m.group(1)) and _month_num(m.group(4)):
        return (
            _iso(int(m.group(3)), _month_num(m.group(1)), int(m.group(2))),
            _iso(int(m.group(6)), _month_num(m.group(4)), int(m.group(5))),
        )

    # "Oct 29 - Nov 2, 2023" — cross month, single trailing year
    m = re.search(_MON + r"\s+(\d{1,2})\s*-\s*" + _MON + r"\s+(\d{1,2}),?\s*(\d{4})", t)
    if m and _month_num(m.group(1)) and _month_num(m.group(3)):
        year = int(m.group(5))
        return (
            _iso(year, _month_num(m.group(1)), int(m.group(2))),
            _iso(year, _month_num(m.group(3)), int(m.group(4))),
        )

    # "July 26-29, 2026" / "October 27 - 31, 2024" — same month
    m = re.search(_MON + r"\s+(\d{1,2})\s*-\s*(\d{1,2}),?\s*(\d{4})", t)
    if m and _month_num(m.group(1)):
        year = int(m.group(4))
        month = _month_num(m.group(1))
        return _iso(year, month, int(m.group(2))), _iso(year, month, int(m.group(3)))

    # "28 Jul 2026 - 30 Jul 2026" — day first, cross endpoints
    m = re.search(
        r"(\d{1,2})\s+" + _MON + r"\s+(\d{4})\s*-\s*(\d{1,2})\s+" + _MON + r"\s+(\d{4})", t
    )
    if m and _month_num(m.group(2)) and _month_num(m.group(5)):
        return (
            _iso(int(m.group(3)), _month_num(m.group(2)), int(m.group(1))),
            _iso(int(m.group(6)), _month_num(m.group(5)), int(m.group(4))),
        )

    # "28 Jul 2026" — single day, day first
    m = re.search(r"(\d{1,2})\s+" + _MON + r"\s+(\d{4})", t)
    if m and _month_num(m.group(2)):
        d = _iso(int(m.group(3)), _month_num(m.group(2)), int(m.group(1)))
        return d, d

    # "Jul 26, 2026" — single day, month first
    m = re.search(_MON + r"\s+(\d{1,2}),?\s*(\d{4})", t)
    if m and _month_num(m.group(1)):
        d = _iso(int(m.group(3)), _month_num(m.group(1)), int(m.group(2)))
        return d, d

    return None, None


def parse_named_date(text):
    """Parse a single ``"Mon D, YYYY"`` date into ``YYYY-MM-DD`` or None.

    Placeholders like ``TBD`` / ``N/A`` return None.
    """
    if not text:
        return None
    if text.strip().upper() in {"TBD", "N/A", "NA", "TBA", ""}:
        return None
    m = re.search(_MON + r"\s+(\d{1,2}),?\s*(\d{4})", text)
    if m and _month_num(m.group(1)):
        return _iso(int(m.group(3)), _month_num(m.group(1)), int(m.group(2)))
    return None


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def _as_date(value):
    """Best-effort parse of a schema date/datetime string to a date object."""
    if not value:
        return None
    text = str(value).strip()
    if len(text) < 10:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _entry_is_upcoming(entry, today):
    """True if any of the entry's dates is today or later, or it is a future year."""
    for key in ("deadline", "abstract_deadline", "start", "end"):
        d = _as_date(entry.get(key))
        if d and d >= today:
            return True
    year = entry.get("year")
    if isinstance(year, int) and year > today.year:
        return True
    return False


def coverage_report(entries, today=None):
    """Report which CSV target venues have (no) upcoming entry.

    Returns a dict with:
      * ``covered``: {target short name -> list of source names}
      * ``missing``: sorted list of target short names with no upcoming entry
      * ``total`` / ``covered_count``: convenience counts
    """
    if today is None:
        today = date.today()

    covered = {}
    for entry in entries:
        canonical = canonical_target(entry.get("title"))
        if canonical and _entry_is_upcoming(entry, today):
            covered.setdefault(canonical, [])
            source = entry.get("source", "unknown")
            if source not in covered[canonical]:
                covered[canonical].append(source)

    all_targets = [t["short"] for t in load_targets()]
    missing = sorted(t for t in all_targets if t not in covered)
    return {
        "covered": covered,
        "missing": missing,
        "total": len(all_targets),
        "covered_count": len(covered),
    }


if __name__ == "__main__":
    targets = load_targets()
    print(f"Loaded {len(targets)} target venues from {os.path.abspath(_CSV_PATH)}")
    for t in targets:
        print(f"  {t['short']:22s} {t['full']}")

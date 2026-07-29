"""Build output.ics from the AI and VLSI conference-deadline parsers.

This replaces the old pipeline that downloaded a dead upstream ICS feed and
merged flaky Selenium scrapes. It now fetches from four normalised parsers,
deduplicates conference editions across sources, and builds the calendar from
scratch with deterministic UIDs so calendar clients do not churn.

Data flow:
  fetch -> merge (dedup by title+year) -> filter stale -> build events ->
  sanity-check -> round-trip validate -> write output.ics
"""

import re
import sys
from datetime import date, datetime, timedelta, timezone

from icalendar import Calendar, Event

from parsers import ai_deadlines, ccf_deadlines, ieee_cas, wikicfp
from parsers.vlsi_coverage import coverage_report
from utils import get_alarms

# Keep an entry/event if a relevant date is no older than this many days, so the
# published calendar stays current without dropping just-passed editions.
STALE_DAYS = 30

OUTPUT_FILE = "output.ics"
UID_DOMAIN = "awesome-conference-dates"

# Source-name constants come from each parser so priorities stay in sync.
AI_SOURCE = ai_deadlines.SOURCE

# Lower number = higher priority when merging duplicate editions. AI entries
# come only from ai-deadlines; the VLSI sources fall back ccf > ieee-cas > wikicfp.
SOURCE_PRIORITY = {
    AI_SOURCE: 0,
    ccf_deadlines.SOURCE: 1,
    ieee_cas.SOURCE: 2,
    wikicfp.SOURCE: 3,
}

# Entry fields filled in field-wise during a merge (title/year identify the group).
MERGEABLE_FIELDS = (
    "full_name", "link", "place", "timezone",
    "deadline", "abstract_deadline", "start", "end",
)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_all():
    """Fetch every source, returning (entries, fetch_counts).

    ai-deadlines and ccf-deadlines are mandatory: a failure aborts the run.
    ieee-cas and wikicfp are supplementary and flakier, so their failures are
    warned about and skipped.
    """
    entries = []
    counts = {}

    for name, parser in (("ai-deadlines", ai_deadlines), ("ccf-deadlines", ccf_deadlines)):
        try:
            fetched = parser.main()
        except Exception as exc:  # mandatory source: cannot continue without it
            print(f"ERROR: mandatory source {name} failed: {exc}")
            sys.exit(1)
        counts[name] = len(fetched)
        entries.extend(fetched)

    for name, parser in (("ieee-cas", ieee_cas), ("wikicfp", wikicfp)):
        try:
            fetched = parser.main()
        except Exception as exc:  # best-effort source: warn loudly and carry on
            print(f"WARNING: supplementary source {name} failed, continuing without it: {exc}")
            counts[name] = 0
            continue
        counts[name] = len(fetched)
        entries.extend(fetched)

    return entries, counts


# ---------------------------------------------------------------------------
# Merging / dedup
# ---------------------------------------------------------------------------

def dedup_key(entry):
    """Identify a conference edition by normalised title + year."""
    title = " ".join(str(entry.get("title", "")).split()).casefold()
    return (title, entry.get("year"))


def _priority(entry):
    return SOURCE_PRIORITY.get(entry.get("source"), 99)


def merge_group(group):
    """Merge duplicate entries: highest-priority source wins, lower ones fill gaps."""
    group = sorted(group, key=_priority)
    base = dict(group[0])
    for other in group[1:]:
        for field in MERGEABLE_FIELDS:
            if not base.get(field) and other.get(field):
                base[field] = other[field]
    return base


def merge_entries(entries):
    """Collapse entries that describe the same edition into one merged entry."""
    groups = {}
    for entry in entries:
        groups.setdefault(dedup_key(entry), []).append(entry)
    return [merge_group(group) for group in groups.values()]


# ---------------------------------------------------------------------------
# Date parsing / staleness
# ---------------------------------------------------------------------------

def parse_datetime(value):
    """Parse "YYYY-MM-DD[ HH:MM:SS]" as a naive local datetime, or None.

    A date without a time is treated as end-of-day, the usual meaning of a
    submission deadline.
    """
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        return None


def parse_day(value):
    """Parse the date portion of a schema string into a date, or None."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def entry_is_current(entry, cutoff):
    """True if any deadline or the conference end date is on/after cutoff."""
    for field in ("abstract_deadline", "deadline", "end"):
        day = parse_day(entry.get(field))
        if day and day >= cutoff:
            return True
    return False


# ---------------------------------------------------------------------------
# Event building
# ---------------------------------------------------------------------------

def slugify(text):
    """Deterministic slug for UIDs: lowercase alphanumerics joined by hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def build_description(entry):
    """Human-readable event description listing the details we have."""
    lines = []
    if entry.get("full_name"):
        lines.append(str(entry["full_name"]))
    if entry.get("place"):
        lines.append(f"Location: {entry['place']}")
    if entry.get("link"):
        lines.append(f"Link: {entry['link']}")
    if entry.get("timezone"):
        # We do not resolve free-form zones (e.g. "AoE", "UTC-7") into VTIMEZONEs;
        # surfacing the raw string lets the user interpret the naive time.
        lines.append(f"Timezone: {entry['timezone']}")
    if entry.get("source"):
        lines.append(f"Source: {entry['source']}")
    return "\n".join(lines)


def _base_event(entry, summary, uid, description):
    event = Event()
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("dtstamp", datetime.now(timezone.utc))
    if description:
        event.add("description", description)
    if entry.get("place"):
        event.add("location", entry["place"])
    return event


def build_deadline_event(entry, kind, when, summary_suffix, uid_suffix):
    """Timed deadline event with reminder alarms attached."""
    slug = slugify(entry["title"])
    year = entry["year"]
    summary = f"{entry['title']} {year} {summary_suffix}"
    uid = f"{slug}-{year}-{uid_suffix}@{UID_DOMAIN}"
    event = _base_event(entry, summary, uid, build_description(entry))
    # Naive datetime => floating local time (no TZID), by design for these feeds.
    event.add("dtstart", when)
    event.add("dtend", when)
    for alarm in get_alarms():
        event.add_component(alarm)
    return event


def build_conference_event(entry, start_day, end_day):
    """All-day conference event; no alarms."""
    slug = slugify(entry["title"])
    year = entry["year"]
    summary = f"{entry['title']} {year}"
    uid = f"{slug}-{year}-conference@{UID_DOMAIN}"
    event = _base_event(entry, summary, uid, build_description(entry))
    event.add("dtstart", start_day)
    # RFC 5545 DTEND for all-day events is exclusive, so add one day past the end.
    event.add("dtend", end_day + timedelta(days=1))
    return event


def build_events(entry, cutoff):
    """Return the events for one entry, skipping any whose date is before cutoff."""
    events = []

    abstract = parse_datetime(entry.get("abstract_deadline"))
    if abstract and abstract.date() >= cutoff:
        events.append(
            build_deadline_event(entry, "abstract", abstract, "abstract deadline", "abstract-deadline")
        )

    deadline = parse_datetime(entry.get("deadline"))
    if deadline and deadline.date() >= cutoff:
        events.append(
            build_deadline_event(entry, "paper", deadline, "deadline", "deadline")
        )

    start_day = parse_day(entry.get("start"))
    end_day = parse_day(entry.get("end"))
    if start_day and end_day and end_day >= cutoff:
        events.append(build_conference_event(entry, start_day, end_day))

    return events


# ---------------------------------------------------------------------------
# Calendar assembly + validation
# ---------------------------------------------------------------------------

def build_calendar(events):
    cal = Calendar()
    cal.add("prodid", "-//luarss//ai-vlsi-deadlines//EN")
    cal.add("version", "2.0")
    for event in events:
        cal.add_component(event)
    return cal


def check_no_duplicate_uids(events):
    uids = [str(event["uid"]) for event in events]
    duplicates = {uid for uid in uids if uids.count(uid) > 1}
    if duplicates:
        print(f"ERROR: duplicate UIDs generated: {sorted(duplicates)}")
        sys.exit(1)


def run_sanity_checks(counts, merged, events):
    """Abort the run if the output looks implausibly thin."""
    ai_fetched = counts.get("ai-deadlines", 0)
    vlsi_fetched = counts.get("ccf-deadlines", 0) + counts.get("ieee-cas", 0) + counts.get("wikicfp", 0)

    if ai_fetched < 30:
        print(f"ERROR: only {ai_fetched} AI entries fetched (need >= 30)")
        sys.exit(1)
    if vlsi_fetched < 15:
        print(f"ERROR: only {vlsi_fetched} VLSI entries fetched (need >= 15)")
        sys.exit(1)
    if len(events) < 40:
        print(f"ERROR: only {len(events)} future events generated (need >= 40)")
        sys.exit(1)

    check_no_duplicate_uids(events)


def validate_ics(ics_bytes):
    """Round-trip parse the generated ICS before writing it to disk."""
    try:
        Calendar.from_ical(ics_bytes)
    except Exception as exc:
        print(f"ERROR: generated ICS failed to round-trip parse: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(counts, merged, events, event_kinds, today):
    print("\n=== Run summary ===")
    print("Fetch counts per source:")
    for name in ("ai-deadlines", "ccf-deadlines", "ieee-cas", "wikicfp"):
        print(f"  {name:15s} {counts.get(name, 0)}")
    print(f"Merged entries: {len(merged)}")
    print(f"Events generated: {len(events)}")
    print(
        f"  abstract deadlines: {event_kinds['abstract']}  "
        f"deadlines: {event_kinds['deadline']}  conferences: {event_kinds['conference']}"
    )
    print(f"  AI events: {event_kinds['ai']}  VLSI events: {event_kinds['vlsi']}")

    report = coverage_report(merged, today)
    print(
        f"\nVLSI coverage: {report['covered_count']}/{report['total']} target venues "
        f"have an upcoming entry."
    )
    if report["missing"]:
        # Coverage gaps are warnings, not failures.
        print("WARNING: no upcoming entry for these target venues:")
        print("  " + ", ".join(report["missing"]))


def count_event_kinds(entries, events, cutoff):
    """Tally event kinds and AI/VLSI split for the summary line."""
    kinds = {"abstract": 0, "deadline": 0, "conference": 0, "ai": 0, "vlsi": 0}
    for event in events:
        uid = str(event["uid"])
        if uid.endswith(f"-abstract-deadline@{UID_DOMAIN}"):
            kinds["abstract"] += 1
        elif uid.endswith(f"-deadline@{UID_DOMAIN}"):
            kinds["deadline"] += 1
        else:
            kinds["conference"] += 1

    ai_keys = {dedup_key(e) for e in entries if e.get("source") == AI_SOURCE}
    for entry in entries:
        n = len(build_events(entry, cutoff))
        if dedup_key(entry) in ai_keys:
            kinds["ai"] += n
        else:
            kinds["vlsi"] += n
    return kinds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    today = date.today()
    cutoff = today - timedelta(days=STALE_DAYS)

    entries, counts = fetch_all()
    merged = merge_entries(entries)
    current = [e for e in merged if entry_is_current(e, cutoff)]

    events = []
    for entry in current:
        events.extend(build_events(entry, cutoff))

    run_sanity_checks(counts, merged, events)

    cal = build_calendar(events)
    ics_bytes = cal.to_ical()
    validate_ics(ics_bytes)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(ics_bytes)

    event_kinds = count_event_kinds(current, events, cutoff)
    print_summary(counts, merged, events, event_kinds, today)
    print(f"\nSuccessfully wrote {len(events)} events to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

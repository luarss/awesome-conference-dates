"""Parser for the IEEE CAS (Circuits and Systems Society) event feed.

The public page https://ieee-cas.org/conference-events/full-conference-list is a
Drupal view with a "Load More" button. The old implementation drove that button
with Selenium, which was flaky (it returned 0, 18 or 36 duplicated events on
different runs and needed a headless browser on the CI runner).

The button is backed by a Drupal views AJAX endpoint (``/views/ajax``) that we
can hit directly with plain ``requests``. The endpoint returns the same block of
upcoming CAS events (~18) deterministically -- the ``page`` pager parameter is
clamped server-side, so a single request is all we need. This removes both
Selenium and the flakiness.

Each event is an ``<article class="simple--event">`` fragment inside the JSON
response, carrying an acronym, title/link, an ISO deadline in a ``<time>`` tag,
a date range and a location.
"""

import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from parsers.vlsi_coverage import canonical_target, is_relevant, parse_date_range

BASE_URL = "https://ieee-cas.org"
AJAX_URL = "https://ieee-cas.org/views/ajax"
SOURCE = "ieee-cas"
TIMEOUT = 30

# View parameters extracted from the page's drupalSettings JSON. The dom-id is a
# stable hash for this particular view/display on the site.
VIEW_PARAMS = {
    "view_name": "content_events",
    "view_display_id": "block_simple_list_filters",
    "view_args": "all/all/all/all",
    "view_dom_id": "8dcff9cdc22b33a400f31665f5afbcd8b9fd24268c5a7edc7c1bcc595e59441c",
    "pager_element": "0",
    "page": "0",
}
HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


def _fetch_events_html():
    """Return the HTML fragment containing the event articles."""
    response = requests.post(AJAX_URL, headers=HEADERS, data=VIEW_PARAMS, timeout=TIMEOUT)
    response.raise_for_status()
    commands = response.json()

    # The Drupal AJAX response is a list of command objects; the event markup
    # lives in an "insert" command whose data contains the article elements.
    for command in commands:
        data = command.get("data")
        if command.get("command") == "insert" and isinstance(data, str) and "simple--event" in data:
            return data
    raise RuntimeError("IEEE CAS response did not contain an event list")


def _text(node):
    return node.get_text(strip=True) if node else None


def _extract_event(article):
    """Extract one event's fields from its <article> element."""
    acronym = _text(article.find("div", class_="field--node--field-acronym"))

    title_tag = article.find("h3", class_="field--node--field-display-title")
    link_tag = title_tag.find("a") if title_tag else None
    full_name = _text(link_tag)
    link = None
    if link_tag and link_tag.get("href"):
        link = urllib.parse.urljoin(BASE_URL, link_tag["href"])

    # Deadline lives in a <time datetime="2026-07-05T12:00:00Z"> tag.
    deadline = None
    deadline_tag = article.find("div", class_="field--node--field-deadline")
    if deadline_tag:
        time_tag = deadline_tag.find("time")
        if time_tag and time_tag.get("datetime"):
            deadline = _format_iso_datetime(time_tag["datetime"])

    # Date range: second span inside the date-range field, e.g. "28 Jul 2026 – 30 Jul 2026".
    start = end = None
    date_tag = article.find("div", class_="field--node--field-date-range")
    if date_tag:
        spans = date_tag.find_all("span")
        if len(spans) > 1:
            start, end = parse_date_range(spans[1].get_text(" ", strip=True))

    place = None
    region_tag = article.find("div", class_="field--node--field-location-text")
    if region_tag:
        spans = region_tag.find_all("span")
        if len(spans) > 1:
            place = spans[1].get_text(strip=True) or None

    return acronym, full_name, link, deadline, start, end, place


def _format_iso_datetime(value):
    """Convert '2026-07-05T12:00:00Z' to '2026-07-05 12:00:00'."""
    try:
        dt = datetime.strptime(value.replace("Z", "").split("+")[0], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value[:10] if len(value) >= 10 else None


def main():
    html = _fetch_events_html()
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("article", class_="simple--event")
    if not articles:
        raise RuntimeError("IEEE CAS returned no event articles")

    entries = []
    seen = set()
    for article in articles:
        acronym, full_name, link, deadline, start, end, place = _extract_event(article)
        if not acronym:
            print("[ieee-cas] skipping event with no acronym")
            continue

        # Deduplicate on link (the pager can repeat the same block).
        key = link or (acronym, deadline)
        if key in seen:
            continue
        seen.add(key)

        # Keep only VLSI/EDA/architecture-relevant venues; map to CSV short name.
        if not is_relevant(acronym):
            continue
        display_title = canonical_target(acronym) or acronym.strip()

        # Derive year from the date range, else from the deadline.
        year = None
        for value in (start, deadline):
            if value and len(value) >= 4 and value[:4].isdigit():
                year = int(value[:4])
                break
        if start and end and end[:4].isdigit():
            year = int(end[:4])
        if year is None:
            print(f"[ieee-cas] skipping {acronym}: no parseable year")
            continue

        entries.append(
            {
                "title": display_title,
                "full_name": full_name,
                "year": year,
                "link": link,
                "deadline": deadline,
                "abstract_deadline": None,
                "timezone": None,
                "place": place,
                "start": start,
                "end": end,
                "source": SOURCE,
            }
        )

    if not entries:
        raise RuntimeError("IEEE CAS parser produced no relevant entries")
    return entries


if __name__ == "__main__":
    data = main()
    print(f"ieee-cas: {len(data)} entries")
    for entry in data:
        print(
            f"  {entry['title']:16s} {entry['year']}  "
            f"deadline={entry['deadline']}  dates={entry['start']}..{entry['end']}  "
            f"{entry['place']}"
        )

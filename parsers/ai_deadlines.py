"""Parser for AI conference deadlines.

Source: the Hugging Face ``ai-deadlines`` project, the actively maintained
successor to the now-dead aideadlin.es. The data lives as one YAML file per
conference under ``src/data/conferences/`` in the GitHub repo, each file
holding a list of per-year entries.

We list the directory once via the GitHub contents API, then fetch each raw
YAML file from the raw.githubusercontent.com CDN (which is not rate limited),
and normalise every entry into a flat dict.
"""

import datetime

import requests
import yaml

SOURCE = "huggingface/ai-deadlines"

# One API call to enumerate the per-conference YAML files. The response gives a
# `download_url` (raw CDN link) for each file, which we then fetch directly.
CONTENTS_API_URL = (
    "https://api.github.com/repos/huggingface/ai-deadlines/"
    "contents/src/data/conferences"
)

# GitHub's API rejects requests without a User-Agent header.
HTTP_HEADERS = {"User-Agent": "awesome-conference-dates/ai-deadlines-parser"}

HTTP_TIMEOUT = 30


def _list_conference_files():
    """Return the list of raw download URLs for every conference YAML file."""
    resp = requests.get(
        CONTENTS_API_URL, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()
    entries = resp.json()
    urls = [
        item["download_url"]
        for item in entries
        if item.get("type") == "file"
        and item.get("name", "").endswith(".yml")
        and item.get("download_url")
    ]
    if not urls:
        raise RuntimeError(
            f"No conference YAML files found at {CONTENTS_API_URL}; "
            "upstream layout may have changed."
        )
    return urls


def _fetch_yaml(url):
    """Fetch and parse a single YAML file into a list of entries."""
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    data = yaml.safe_load(resp.text)
    # Each file is expected to be a list of conference-year entries.
    return data if isinstance(data, list) else []


def _to_date_str(value):
    """Normalise a date/datetime/str into a "YYYY-MM-DD[ HH:MM:SS]" string.

    Returns None for empty or non-date-looking values (e.g. "TBD").
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    # Upstream deadlines are quoted ISO strings; guard against stray "TBD" etc.
    if len(text) >= 10 and text[:4].isdigit() and text[4] == "-" and text[7] == "-":
        return text
    return None


def _extract_deadlines(entry):
    """Pull (paper_deadline, abstract_deadline, timezone) out of an entry.

    Handles both the modern schema (a ``deadlines`` list of typed items) and
    the legacy schema (a scalar ``deadline`` plus entry-level ``timezone``).
    """
    deadlines = entry.get("deadlines")
    if isinstance(deadlines, list):
        # Upstream spells the main paper deadline as either "paper" or
        # "submission"; prefer "paper" when both are present.
        paper = paper_fallback = abstract = None
        paper_tz = paper_fallback_tz = abstract_tz = None
        for item in deadlines:
            if not isinstance(item, dict):
                continue
            date_str = _to_date_str(item.get("date"))
            if date_str is None:
                continue
            item_type = item.get("type")
            tz = str(item["timezone"]).strip() if item.get("timezone") else None
            if item_type == "paper" and paper is None:
                paper, paper_tz = date_str, tz
            elif item_type == "submission" and paper_fallback is None:
                paper_fallback, paper_fallback_tz = date_str, tz
            elif item_type == "abstract" and abstract is None:
                abstract, abstract_tz = date_str, tz
        if paper is None:
            paper, paper_tz = paper_fallback, paper_fallback_tz
        timezone = paper_tz or abstract_tz
        return paper, abstract, timezone

    # Legacy scalar schema.
    paper = _to_date_str(entry.get("deadline"))
    abstract = _to_date_str(entry.get("abstract_deadline"))
    timezone = entry.get("timezone")
    timezone = str(timezone).strip() if timezone else None
    return paper, abstract, timezone


def _build_place(entry):
    """Compose a human-readable location from city/country (or legacy place)."""
    if entry.get("place"):
        return str(entry["place"]).strip()
    parts = [str(entry[k]).strip() for k in ("city", "country") if entry.get(k)]
    return ", ".join(parts) if parts else None


def _normalize(entry):
    """Normalise one upstream entry, or return None if it should be skipped."""
    title = entry.get("title")
    year = entry.get("year")
    if not title or year is None:
        print(f"WARNING: skipping entry missing title/year: {entry.get('id', entry)}")
        return None
    try:
        year = int(year)
    except (TypeError, ValueError):
        print(f"WARNING: skipping entry with non-integer year: {entry.get('id', year)}")
        return None

    deadline, abstract_deadline, timezone = _extract_deadlines(entry)
    if deadline is None and abstract_deadline is None:
        print(f"WARNING: skipping {title} {year}: no usable deadline")
        return None

    return {
        "title": str(title).strip(),
        "full_name": str(entry["full_name"]).strip() if entry.get("full_name") else None,
        "year": year,
        "link": str(entry["link"]).strip() if entry.get("link") else None,
        "deadline": deadline,
        "abstract_deadline": abstract_deadline,
        "timezone": timezone,
        "place": _build_place(entry),
        "start": _to_date_str(entry.get("start")),
        "end": _to_date_str(entry.get("end")),
        "source": SOURCE,
    }


def main():
    """Fetch and normalise AI conference deadlines.

    Raises on fetch failure or if zero valid entries are produced, so the
    integration layer never publishes an empty calendar silently.
    """
    urls = _list_conference_files()

    results = []
    for url in urls:
        try:
            entries = _fetch_yaml(url)
        except (requests.RequestException, yaml.YAMLError) as exc:
            print(f"WARNING: failed to fetch/parse {url}: {exc}")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                print(f"WARNING: skipping non-dict entry in {url}")
                continue
            normalized = _normalize(entry)
            if normalized is not None:
                results.append(normalized)

    if not results:
        raise RuntimeError(
            "AI deadlines parser produced zero valid entries "
            f"from {SOURCE}; refusing to return an empty list."
        )
    return results


if __name__ == "__main__":
    data = main()
    print(f"Fetched {len(data)} entries")
    for conf in data[:5]:
        print(conf)

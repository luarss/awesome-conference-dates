"""Parser for the ccf-deadlines dataset (github.com/ccfddl/ccf-deadlines).

ccf-deadlines keeps one hand-maintained YAML file per conference series, which
is far more reliable than scraping individual conference sites. We download the
whole repository as a single gzipped tarball (one HTTP request), parse every
``conference/**/*.yml`` file, and keep the VLSI / EDA / architecture venues that
match our target list.

Each YAML series looks like::

    - title: DAC
      description: Design Automation Conference
      confs:
        - year: 2026
          link: https://dac.com/2026/call-for-contributions
          timeline:
            - abstract_deadline: '2025-11-11 17:00:00'
              deadline: '2025-11-18 17:00:00'
          timezone: UTC-8
          date: July 26-29, 2026
          place: Long Beach, CA
"""

import io
import tarfile
from datetime import datetime

import requests
import yaml

from parsers.vlsi_coverage import canonical_target, is_relevant, parse_date_range

# codeload serves a tarball of the default branch in a single request, which
# avoids hitting the GitHub API rate limit or fetching dozens of raw files.
TARBALL_URL = "https://codeload.github.com/ccfddl/ccf-deadlines/tar.gz/refs/heads/main"
SOURCE = "ccf-deadlines"
TIMEOUT = 60


def _download_series():
    """Yield each parsed YAML document from the ccf-deadlines conference/ tree."""
    response = requests.get(TARBALL_URL, timeout=TIMEOUT)
    response.raise_for_status()

    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
        for member in tar.getmembers():
            if "/conference/" not in member.name or not member.name.endswith(".yml"):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            try:
                # Each file is a list of series (usually exactly one).
                for series in yaml.safe_load(handle.read()) or []:
                    yield member.name, series
            except yaml.YAMLError as exc:
                print(f"[ccf] skipping malformed YAML {member.name}: {exc}")


def _clean_deadline(value):
    """Return a deadline string, or None for missing / placeholder values."""
    if not value:
        return None
    text = str(value).strip()
    if text.upper() in {"TBD", "N/A", "NA", "TBA", ""}:
        return None
    return text


def _extract_deadlines(timeline):
    """Pull the (paper, abstract) deadlines out of a conf's timeline list.

    The timeline is a list of dicts that may carry an ``abstract_deadline``
    key, a ``deadline`` key, and/or a free-text ``comment``. We prefer a
    deadline whose comment mentions the paper/full submission; otherwise we
    take the last plain deadline (typically the final paper deadline).
    """
    abstract = None
    paper = None
    generic = []
    for item in timeline or []:
        if not isinstance(item, dict):
            continue
        abstract = _clean_deadline(item.get("abstract_deadline")) or abstract
        deadline = _clean_deadline(item.get("deadline"))
        if not deadline:
            continue
        comment = (item.get("comment") or "").lower()
        if "abstract" in comment and not item.get("abstract_deadline"):
            abstract = abstract or deadline
        elif any(word in comment for word in ("paper", "full", "submission")):
            paper = deadline
        else:
            generic.append(deadline)
    if paper is None and generic:
        paper = generic[-1]
    return paper, abstract


def main():
    current_year = datetime.now().year
    entries = []

    for filename, series in _download_series():
        if not isinstance(series, dict):
            continue
        title = series.get("title")
        if not title or not is_relevant(title):
            continue

        # Normalise the short name to the CSV spelling when it is a target.
        display_title = canonical_target(title) or title
        full_name = series.get("description")

        for conf in series.get("confs") or []:
            if not isinstance(conf, dict):
                continue
            year = conf.get("year")
            if not isinstance(year, int):
                print(f"[ccf] skipping {title} conf with bad year in {filename}")
                continue
            if year < current_year:
                continue  # keep only current/future editions

            paper, abstract = _extract_deadlines(conf.get("timeline"))
            start, end = parse_date_range(conf.get("date"))

            entries.append(
                {
                    "title": display_title,
                    "full_name": full_name,
                    "year": year,
                    "link": conf.get("link"),
                    "deadline": paper,
                    "abstract_deadline": abstract,
                    "timezone": conf.get("timezone"),
                    "place": conf.get("place"),
                    "start": start,
                    "end": end,
                    "source": SOURCE,
                }
            )

    if not entries:
        raise RuntimeError("ccf-deadlines parser produced no entries")
    return entries


if __name__ == "__main__":
    data = main()
    print(f"ccf-deadlines: {len(data)} entries")
    for entry in data:
        print(
            f"  {entry['title']:16s} {entry['year']}  "
            f"deadline={entry['deadline']}  dates={entry['start']}..{entry['end']}  "
            f"{entry['place']}"
        )

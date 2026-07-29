"""Parser for WikiCFP (wikicfp.com) conference-series pages.

WikiCFP is used as a fallback for VLSI / EDA / test / circuits venues that are
not covered by the more reliable ccf-deadlines dataset or the IEEE CAS feed
(e.g. ISSCC, CICC, ISPD, ISQED, ISVLSI, VTS, ...).

WikiCFP's free-text search is JavaScript-gated, but each conference *series*
has a stable numeric id whose ``program`` page is plain server-rendered HTML
that lists every edition with its dates, location and deadline inline. We keep
a curated acronym -> series-id map (built from WikiCFP's own series index by
exact-acronym match, which avoids the predatory-conference noise that plagues
WikiCFP's category browse). One request per venue, rate-limited and polite.

A program page row for an edition looks like::

    <a ...event.showcfp?eventid=189547...>ISPD 2026</a>   (rowspan 2)
    International Symposium on Physical Design               (colspan 3)
    Mar 15, 2026 - Mar 18, 2026 | Bonn, Germany | Sep 28, 2025 (Sep 21, 2025)
                                                   ^deadline  ^abstract deadline
"""

import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from parsers.vlsi_coverage import canonical_target, parse_date_range, parse_named_date

BASE_URL = "http://www.wikicfp.com/cfp/program"
SOURCE = "wikicfp"
TIMEOUT = 20
REQUEST_DELAY = 1.0  # seconds between requests, to stay polite to WikiCFP
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# Curated map of target acronym -> WikiCFP conference-series id. Built by
# exact-acronym matching against WikiCFP's series index. The remaining CSV
# venues are either not on WikiCFP or are covered by ccf-deadlines / IEEE CAS.
SERIES_IDS = {
    "DAC": "634",
    "DATE": "653",
    "ICCAD": "1297",
    "ICCD": "1304",
    "ICECS": "1349",
    "ISPD": "1741",
    "ISSCC": "1751",
    "ISQED": "1746",
    "ISLPED": "1723",
    "ISVLSI": "1766",
    "ISCA": "1683",
    "ISCAS": "1684",
    "CICC": "451",
    "CF": "418",
    "ASAP": "229",
    "ASP-DAC": "241",
    "ARITH": "218",
    "FPGA": "1082",
    "GLSVLSI": "1139",
    "MICRO": "2052",
    "VTS": "2981",
    "VLSI-SoC": "2958",
    "SiPS": "2687",
    "SoCC": "2720",
    "SAMOS": "2543",
    "ESSCIRC": "924",
    "Euromicro DSD": "762",
}


def _parse_deadline(text):
    """WikiCFP shows ``"Sep 28, 2025 (Sep 21, 2025)"`` = deadline (abstract)."""
    if not text:
        return None, None
    match = re.match(r"\s*(.*?)\s*(?:\(([^)]*)\))?\s*$", text)
    deadline = parse_named_date(match.group(1)) if match else None
    abstract = parse_named_date(match.group(2)) if match and match.group(2) else None
    return deadline, abstract


def _parse_editions(html):
    """Yield ``(name, when, where, deadline_text)`` per edition on a program page."""
    soup = BeautifulSoup(html, "html.parser")
    current = None
    for row in soup.find_all("tr"):
        link = row.find("a", href=re.compile(r"event\.showcfp"))
        cells = row.find_all("td")
        if link and cells:
            current = {"name": link.get_text(strip=True)}
        elif current and len(cells) == 3:
            current["when"] = cells[0].get_text(strip=True)
            current["where"] = cells[1].get_text(strip=True)
            current["deadline"] = cells[2].get_text(" ", strip=True)
            yield current
            current = None


def _year_from_name(name):
    match = re.search(r"\b(20\d{2})\b", name or "")
    return int(match.group(1)) if match else None


def main():
    current_year = datetime.now().year
    entries = []
    failures = 0

    for acronym, series_id in SERIES_IDS.items():
        try:
            response = requests.get(
                BASE_URL,
                params={"id": series_id, "s": acronym},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[wikicfp] failed to fetch {acronym} (id {series_id}): {exc}")
            failures += 1
            time.sleep(REQUEST_DELAY)
            continue

        display_title = canonical_target(acronym) or acronym
        full_name = None

        for edition in _parse_editions(response.text):
            year = _year_from_name(edition["name"])
            if year is None or year < current_year:
                continue  # keep only current/future editions
            deadline, abstract = _parse_deadline(edition.get("deadline", ""))
            start, end = parse_date_range(edition.get("when", ""))
            place = edition.get("where") or None
            if place and place.upper() in {"N/A", "TBD"}:
                place = None

            entries.append(
                {
                    "title": display_title,
                    "full_name": full_name,
                    "year": year,
                    "link": f"http://www.wikicfp.com/cfp/program?id={series_id}",
                    "deadline": deadline,
                    "abstract_deadline": abstract,
                    "timezone": None,
                    "place": place,
                    "start": start,
                    "end": end,
                    "source": SOURCE,
                }
            )

        time.sleep(REQUEST_DELAY)

    # If every single request failed, the source is down; raise rather than
    # silently returning nothing.
    if failures == len(SERIES_IDS):
        raise RuntimeError("wikicfp parser: all series requests failed")
    if not entries:
        raise RuntimeError("wikicfp parser produced no upcoming entries")
    return entries


if __name__ == "__main__":
    data = main()
    print(f"wikicfp: {len(data)} entries")
    for entry in data:
        print(
            f"  {entry['title']:16s} {entry['year']}  "
            f"deadline={entry['deadline']}  abstract={entry['abstract_deadline']}  "
            f"dates={entry['start']}..{entry['end']}  {entry['place']}"
        )

"""Build backend/app/refdata/data/rating_schedule.json from the eCFR API
(38 CFR Part 4, the VA Schedule for Rating Disabilities).

Usage:  python scripts/build_rating_schedule.py [YYYY-MM-DD]

Parses the schedule's rating tables: each diagnostic code row ("6260
Tinnitus, recurrent") starts an entry; following indented criteria rows with a
percent cell become that code's rating tiers."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path

OUT = (Path(__file__).parent.parent / "backend" / "app" / "refdata" / "data"
       / "rating_schedule.json")

# mental-disorder DCs are listed as <FP-2> paragraphs and share the General
# Rating Formula for Mental Disorders (§4.130)
FP_RE = re.compile(r"<FP-2>(.*?)</FP-2>", re.S)
MENTAL_TIERS = [
    {"percent": 100, "criteria": "Total occupational and social impairment"},
    {"percent": 70, "criteria": "Deficiencies in most areas (work, school, family, judgment, thinking, mood)"},
    {"percent": 50, "criteria": "Reduced reliability and productivity"},
    {"percent": 30, "criteria": "Occasional decrease in work efficiency, intermittent inability to perform tasks"},
    {"percent": 10, "criteria": "Mild or transient symptoms controlled by continuous medication"},
    {"percent": 0, "criteria": "Diagnosed, symptoms not severe enough to interfere or require medication"},
]

ROW_RE = re.compile(r"<TR>(.*?)</TR>", re.S)
TD_RE = re.compile(r"<TD[^>]*>(.*?)</TD>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
DC_RE = re.compile(r"^(\d{4})\s+(.{3,})")


def _clean(cell: str) -> str:
    return unescape(TAG_RE.sub(" ", cell)).replace("\n", " ").strip(" .:—").strip()


def parse(xml: str) -> dict[str, dict]:
    codes: dict[str, dict] = {}
    current: dict | None = None
    for row in ROW_RE.findall(xml):
        cells = TD_RE.findall(row)
        if not cells:
            continue
        left = _clean(cells[0])
        right = _clean(cells[-1]) if len(cells) > 1 else ""
        if not left or left.lower().startswith(("note", "general rating formula")):
            continue
        percent = int(right) if right.isdigit() and 0 <= int(right) <= 100 else None

        m = DC_RE.match(left)
        if m and not left.startswith(("38 ", "19")):  # avoid years/citations
            dc, name = m.group(1), _clean(m.group(2))
            current = codes.setdefault(dc, {"name": name, "tiers": []})
            if percent is not None:
                current["tiers"].append({"percent": percent, "criteria": name})
        elif current is not None and percent is not None and len(left) > 3:
            current["tiers"].append({"percent": percent, "criteria": left[:500]})
    # mental-disorder codes (9200-9599) from FP-2 paragraphs share §4.130 tiers
    for para in FP_RE.findall(xml):
        m = DC_RE.match(_clean(para))
        if m and m.group(1).startswith("9") and "[Removed]" not in para:
            dc, name = m.group(1), _clean(m.group(2))
            if dc not in codes or not codes[dc]["tiers"]:
                codes[dc] = {"name": name, "tiers": list(MENTAL_TIERS)}

    # keep tiers sorted high→low, dedup percents keeping first criteria text
    for entry in codes.values():
        seen, tiers = set(), []
        for t in sorted(entry["tiers"], key=lambda t: -t["percent"]):
            if t["percent"] not in seen:
                tiers.append(t)
                seen.add(t["percent"])
        entry["tiers"] = tiers
    return codes


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().replace(day=1).isoformat()
    url = f"https://www.ecfr.gov/api/versioner/v1/full/{date}/title-38.xml?part=4"
    print(f"fetching {url}")
    with urllib.request.urlopen(url) as r:
        xml = r.read().decode("utf-8", "replace")
    codes = parse(xml)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"source": url, "built": dt.date.today().isoformat(), "codes": codes},
        indent=1), encoding="utf-8")
    with_tiers = sum(1 for c in codes.values() if c["tiers"])
    print(f"wrote {OUT}: {len(codes)} diagnostic codes ({with_tiers} with rating tiers)")


if __name__ == "__main__":
    main()

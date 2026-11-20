import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kb.facts import read_facts, write_facts  # noqa: E402

PREFIX = "repeats on "
DATES = re.compile(r"\d{4}-\d{2}-\d{2}")
SERIES = ("person", "domain", "kind", "entity", "summary", "time", "source")
SAME = ("person", "domain", "kind", "entity", "summary", "time", "amount", "due", "contact", "link")


def dates_of(fact):
    if fact["value"].startswith(PREFIX):
        return DATES.findall(fact["value"].split(":", 1)[1])
    return [fact["date"]]


def key_of(fact):
    if fact["source"].startswith("calendar:"):
        return ("calendar",) + tuple(fact[k] for k in SERIES)
    if fact["value"] and not fact["value"].startswith(PREFIX):
        return ("own value", fact["id"])
    return ("other",) + tuple(fact[k] for k in SAME)


def collapse(facts, least=3):
    groups = {}
    for fact in facts:
        groups.setdefault(key_of(fact), []).append(fact)
    merged = {}
    for name, rows in groups.items():
        days = sorted({day for row in rows for day in dates_of(row)})
        if len(rows) < 2 or len(days) < (least if name[0] == "calendar" else 2):
            continue
        keep = min(rows, key=lambda row: (row["date"], row["id"]))
        sources = list(dict.fromkeys(ref for row in sorted(rows, key=lambda r: r["date"]) for ref in row["source"].split()))
        keep.update(date=days[0], value=f"{PREFIX}{len(days)} dates: {' '.join(days)}", source=" ".join(sources))
        if name[0] == "calendar":
            keep["due"] = ""
        for row in rows:
            if row is not keep:
                merged[row["id"]] = keep["id"]
    return [fact for fact in facts if fact["id"] not in merged], merged


def relink(path, merged):
    if not path.exists() or not merged:
        return
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    seen, kept = set(), []
    for row in rows:
        row["fact"] = merged.get(row.get("fact", ""), row.get("fact", ""))
        key = tuple(row.values())
        if key not in seen:
            seen.add(key)
            kept.append(row)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)


if __name__ == "__main__":
    facts, merged = collapse(read_facts())
    write_facts(facts)
    relink(REPO / "documents/fact-links.csv", merged)
    print(f"{len(merged)} repeat rows folded into their series")

import csv
import re

from kb.schema import FACT_COLUMNS, FACTS_DIR


def year_of(fact):
    return fact["date"][:4] if re.match(r"\d{4}", fact["date"]) else "undated"


def read_facts(directory=FACTS_DIR):
    facts = []
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="") as handle:
            facts.extend(csv.DictReader(handle))
    return facts


def write_facts(facts, directory=FACTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
    by_year = {}
    for fact in facts:
        by_year.setdefault(year_of(fact), []).append(fact)
    for stale in directory.glob("*.csv"):
        if stale.stem not in by_year:
            stale.unlink()
    for year, rows in by_year.items():
        rows.sort(key=lambda fact: (fact["date"], fact["time"], fact["id"]))
        with (directory / f"{year}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, FACT_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def next_id(facts):
    highest = max((int(fact["id"][1:]) for fact in facts), default=0)
    return f"F{highest + 1:06d}"


def new_fact(**fields):
    unknown = set(fields) - set(FACT_COLUMNS)
    if unknown:
        raise ValueError(f"unknown fact columns: {sorted(unknown)}")
    return {column: str(fields.get(column, "")).strip() for column in FACT_COLUMNS}

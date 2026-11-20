import csv
import datetime
import hashlib
import json
from pathlib import Path
from kb import household  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
STATE = household.STATE / "digest-state.json"
WATCH = ("grade", "assignment", "appointment", "event", "alert", "bill", "statement", "invoice", "autopay", "form", "trip", "teacher_message", "message", "attendance")


def facts(root=REPO):
    rows = {}
    for path in sorted((root / "facts").glob("*.csv")):
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                rows[row["id"]] = row
    return rows


def digest_of(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]


def changed(rows, state):
    before = state.get("facts", {})
    return [row for code, row in rows.items() if before.get(code) != digest_of(row)] if before else []


def worth(row):
    if row["domain"] == "job" or row["source"].startswith("calendar:"):
        return False
    if row["kind"] == "grade":
        return row["value"].startswith("0/") or "missing" in row["summary"].lower() or "late" in row["summary"].lower()
    return row["kind"] in WATCH


def line(row):
    who = row["person"] if row["person"] not in ("", "household", "other") else "Household"
    return f"- {who}: {row['summary']} ({row['id']})"


def build(rows, state, today, upcoming):
    fresh = [row for row in changed(rows, state) if worth(row)]
    parts = [f"Household digest for {today:%A %B %-d}"]
    today_events = [e for e in upcoming if e["day"] == today.isoformat()]
    week = [e for e in upcoming if today.isoformat() < e["day"] <= (today + datetime.timedelta(days=7)).isoformat()]
    if today_events:
        parts.append("\nToday\n" + "\n".join(f"- {e['time'] or 'all day'}: {e['title']}" for e in today_events))
    if week:
        parts.append("\nNext 7 days\n" + "\n".join(f"- {e['day'][5:]}: {e['title']}" for e in week))
    if fresh:
        parts.append(f"\nNew or changed since the last digest ({len(fresh)})\n" + "\n".join(line(row) for row in fresh[:40]))
    if len(parts) == 1:
        parts.append("\nNothing new and nothing due this week.")
    return "\n".join(parts)


def run(today=None, state_path=STATE, root=REPO):
    from kb import agent_calendar
    today = today or datetime.date.today()
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    rows = facts(root)
    upcoming = agent_calendar.wanted(root / ".kb/kb.sqlite", today, days=8)
    text = build(rows, state, today, upcoming)
    state_path.write_text(json.dumps({"day": today.isoformat(), "facts": {code: digest_of(row) for code, row in rows.items()}}))
    return text

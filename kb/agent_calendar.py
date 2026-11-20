import datetime
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from kb import household  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CALENDAR = "Agent events"
STATE = household.STATE / "agent-calendar.json"
QUERY = """select id, coalesce(nullif(due, ''), date) as day, time, person, kind, entity, summary, source from facts
where coalesce(nullif(due, ''), date) between ? and ? and source not like 'calendar:%'
order by day, time, id"""
KINDS = ("assignment", "appointment", "event", "trip", "subscription", "alert", "form", "deadline", "test", "exam", "quiz",
         "renewal", "reservation", "flight", "schedule", "registration", "payment_due", "bill", "social", "reminder",
         "notice", "medication", "fee", "vaccine", "license", "passport", "warranty", "health plan")
BILLS = ("statement", "invoice", "autopay", "payment", "receipt")
EVENT = {"event": {"type": "noul", "instructions": "The `fact` names something on its date that a person attends, must do, must pay, or that starts, ends, expires or is due. A grade, a score, a policy, a message someone sent or a past purchase is not one."}}
EXPIRES = ("license", "passport", "warranty", "health plan", "receipt", "vaccine")


def judged(rows):
    from kb import jev
    states = [{"fact": f"{r[1]} {r[2] or ''} {r[3] or ''} [{r[4]}] {r[5] or ''}: {r[6]}"} for r in rows]
    return [answers["event"]["noul"] >= 0.8 for answers in jev.ask_many(states, EVENT)]


def wanted(index, today, days=None, judge=judged):
    con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    end = (today + datetime.timedelta(days=days)).isoformat() if days else "9999-12-31"
    rows = con.execute(QUERY, (today.isoformat(), end)).fetchall()
    sure = [r for r in rows if r[4] in KINDS or (r[4] in BILLS and _due(con, r[0]))]
    unsure = [r for r in rows if r not in sure]
    keep = set(sure) | {r for r, yes in zip(unsure, judge(unsure) if unsure else []) if yes}
    found, seen = [], set()
    for i, d, t, p, k, e, s, src in (r for r in rows if r in keep):
        name = title(p, k, e, s)
        if (d, name) in seen:
            continue
        seen.add((d, name))
        found.append({"id": i, "day": d, "time": "" if (t or "").startswith("23:59") else (t or ""), "title": name,
                      "notes": f"{course(e)}\n{s}\n{k} fact {i}, source: {src}".strip()})
    return found


def _due(con, code):
    return bool(con.execute("select due from facts where id = ?", (code,)).fetchone()[0])


def course(entity):
    name = re.sub(r"^P\d+\s*-\s*", "", entity or "")
    return re.sub(r"\s*-\s*[A-Z][A-Za-z'.]+(\s*-\s*\d{4})?$|\s*-\s*\d{4}$", "", name).strip()


def title(person, kind, entity, summary):
    who = "Household" if person in ("", None, "household", "other") else person
    if kind == "assignment":
        work = re.split(r":\s*due \d{4}-\d{2}-\d{2}", summary)[0].strip()
        work = re.sub(r"^\d{1,2}/\d{1,2}/\d{2,4}\s*-?\s*", "", work).strip()
        return f"{who}: Due {work} ({course(entity)})"[:250]
    if kind in EXPIRES:
        label = "Due again" if kind == "vaccine" else "Ends"
        return f"{who}: {label}: {summary}"[:250]
    if entity and entity.lower() not in summary.lower() and entity.lower() != "other":
        return f"{who}: {course(entity)}: {summary}"[:250]
    return f"{who}: {summary}"[:250]


def quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def script(events, today):
    lines = [f'tell application "Calendar"',
             f'if not (exists calendar {quote(CALENDAR)}) then make new calendar with properties {{name:{quote(CALENDAR)}}}',
             f'set target to calendar {quote(CALENDAR)}',
             f'set floor to (current date) - (2 * days)',
             'delete (every event of target whose start date is greater than floor)']
    for e in events:
        y, m, d = (int(x) for x in e["day"].split("-"))
        hour, minute = (int(x) for x in e["time"].split(":")[:2]) if e["time"] else (0, 0)
        lines += ['set s to current date', f'set year of s to {y}', 'set day of s to 1', f'set month of s to {m}', f'set day of s to {d}',
                  f'set time of s to {hour * 3600 + minute * 60}']
        if e["time"]:
            lines.append(f'make new event at end of events of target with properties {{summary:{quote(e["title"])}, start date:s, end date:s + (60 * minutes), description:{quote(e["notes"])}}}')
        else:
            lines.append(f'make new event at end of events of target with properties {{summary:{quote(e["title"])}, start date:s, end date:s, allday event:true, description:{quote(e["notes"])}}}')
    lines.append("end tell")
    return "\n".join(lines)


def sync(index=REPO / ".kb/kb.sqlite", state=STATE, run=subprocess.run, digest=None):
    today = datetime.date.today()
    events = wanted(index, today)
    if digest:
        events.insert(0, {"id": "digest", "day": today.isoformat(), "time": "07:00", "title": "Household digest", "notes": digest})
    digest = hashlib.sha256(json.dumps([today.isoformat(), events]).encode()).hexdigest()
    if state.exists() and json.loads(state.read_text()).get("digest") == digest:
        return 0
    run(["osascript", "-"], input=script(events, today), text=True, check=True, timeout=600)
    state.write_text(json.dumps({"digest": digest, "events": len(events)}))
    return len(events)


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    text = None
    if "--digest" in sys.argv:
        from kb import digest
        last = json.loads(digest.STATE.read_text()).get("day") if digest.STATE.exists() else None
        saved = household.STATE / "digest-today.txt"
        if last != datetime.date.today().isoformat():
            saved.write_text(digest.run())
        text = saved.read_text()
    print(sync(digest=text), "events written to", CALENDAR, file=sys.stderr)

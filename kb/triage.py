from kb import jev
from kb.household import AREAS

HOUSEHOLD = {"household": {"type": "noul", "instructions": "The `message` carries a fact about the family or its plans, such as home, health, school, activities, travel, money, pets or purchases."}}
CHOICES = {**{name: area.get("about", name) for name, area in AREAS.items()}, "other": "Chatter that fits no area."}


def questions():
    return {"domain": {"type": "choice", "instructions": "Which household area does the `message` belong to?", "criteria": CHOICES}, **HOUSEHOLD}


def message_of(row):
    who = row.get("from") or ("me" if row.get("from_me") else row.get("handle", ""))
    where = row.get("channel") or row.get("handle") or ""
    return f"{where} | {who}: {row.get('text', '')}"[:1500]


def tag(rows, ask=None):
    ask = ask or (lambda states: jev.ask_many(states, questions()))
    answers = ask([{"message": message_of(r)} for r in rows])
    tagged = [{**r, "jev": {"domain": a["domain"]["choice"], "household": round(a["household"]["noul"], 3)}} for r, a in zip(rows, answers)]
    return sorted(tagged, key=lambda r: -r["jev"]["household"])


def counts(rows, high=0.5, low=0.2):
    scores = [r["jev"]["household"] for r in rows if r.get("jev")]
    return {"high": sum(s >= high for s in scores), "low": sum(s < low for s in scores), "total": len(rows)}

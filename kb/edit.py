import datetime

from kb.facts import new_fact, next_id, read_facts, write_facts
from kb.schema import DOMAINS, FACTS_DIR, PEOPLE, REPO, SOURCE_PREFIXES

def is_date(text):
    try:
        return datetime.date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False


def problems(fact, repo=REPO):
    found = []
    if not is_date(fact["date"]):
        found.append(f"date {fact['date']!r} is not YYYY-MM-DD")
    if fact["person"] not in PEOPLE:
        found.append(f"person {fact['person']!r} is not one of {[p for p in PEOPLE if p]}")
    if fact["domain"] not in DOMAINS:
        found.append(f"domain {fact['domain']!r} is not one of {DOMAINS}")
    if not fact["kind"] or not fact["summary"]:
        found.append("kind and summary are required")
    whole = fact["source"].startswith(("calendar:", "file:"))
    if not fact["source"] or not all(part.startswith(SOURCE_PREFIXES) for part in ([fact["source"]] if whole else fact["source"].split(" "))):
        found.append(f"source {fact['source']!r} must start with one of {SOURCE_PREFIXES}")
    if fact["link"] and not (repo / f"{fact['link']}.md").exists():
        found.append(f"link {fact['link']!r} names no record file")
    if fact["amount"]:
        try:
            float(fact["amount"])
        except ValueError:
            found.append(f"amount {fact['amount']!r} is not a number")
    return found


def add_facts(rows, repo=REPO):
    directory = repo / FACTS_DIR.name
    facts = read_facts(directory)
    known = {(f["date"], f["time"], f["person"], f["domain"], f["summary"], f["source"]) for f in facts}
    added, skipped = [], []
    for row in rows:
        fact = new_fact(**row)
        errors = problems(fact, repo)
        if errors:
            raise ValueError(f"{row}: {'; '.join(errors)}")
        key = (fact["date"], fact["time"], fact["person"], fact["domain"], fact["summary"], fact["source"])
        if key in known:
            skipped.append(fact)
            continue
        fact["id"] = next_id(facts)
        facts.append(fact)
        known.add(key)
        added.append(fact)
    write_facts(facts, directory)
    return added, skipped

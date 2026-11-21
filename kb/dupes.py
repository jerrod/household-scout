import csv
import difflib
import re
from collections import defaultdict
from pathlib import Path

from kb import jev
from kb.facts import read_facts, write_facts
from kb.schema import FACT_COLUMNS, FACTS_DIR, REPO

THRESHOLD = 0.9
SIMILAR = 0.6
SAME = {"noul": {"type": "noul", "instructions": "Do `fact_a` and `fact_b` record the same event or item?"}}
SKIP_DIRS = {".git", ".kb", "inbox", "facts", "server", "vault", "secrets", "node_modules", "archive"}
ID = re.compile(r"\bF\d{6}\b")


def candidates(facts):
    groups = defaultdict(list)
    for fact in facts:
        if not fact["value"].startswith("repeats on "):
            groups[(fact["date"], fact["person"])].append(fact)
    found = []
    for rows in groups.values():
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                ratio = difflib.SequenceMatcher(None, a["summary"].lower(), b["summary"].lower()).ratio()
                same = a["entity"] and a["entity"] == b["entity"] and a["kind"] == b["kind"]
                if ratio >= SIMILAR or same:
                    found.append((a, b))
    return found


def line(fact):
    return f"{fact['date']} {fact['person']} [{fact['kind']}] {fact['entity']}: {fact['summary']} {fact['value']}".strip()


def find(facts, ask=None):
    pairs = candidates(facts)
    ask = ask or (lambda states: jev.ask_many(states, SAME))
    answers = ask([{"fact_a": line(a), "fact_b": line(b)} for a, b in pairs]) if pairs else []
    found = [{"keep": min(a["id"], b["id"]), "drop": max(a["id"], b["id"]), "score": r["noul"]["noul"], "a": a["summary"], "b": b["summary"]} for (a, b), r in zip(pairs, answers) if r["noul"]["noul"] >= THRESHOLD]
    return sorted(found, key=lambda p: -p["score"])


def merged(keep, drop):
    row = dict(keep)
    row["source"] = " ".join(dict.fromkeys((keep["source"] + " " + drop["source"]).split()))
    for column in FACT_COLUMNS:
        if not row[column]:
            row[column] = drop[column]
    return row


def mapping(pairs):
    parent = {}

    def root(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for p in pairs:
        a, b = root(p["keep"]), root(p["drop"])
        if a != b:
            parent[max(a, b)] = min(a, b)
    return {x: root(x) for x in parent if root(x) != x}


def rewrite_references(moved, root=REPO):
    for path in Path(root).rglob("*"):
        parts = set(path.relative_to(root).parts[:-1])
        if parts & SKIP_DIRS or path.suffix not in (".md", ".csv") or not path.is_file():
            continue
        text = path.read_text()
        new = ID.sub(lambda m: moved.get(m.group(0), m.group(0)), text)
        if path.name == "fact-links.csv":
            rows = list(csv.reader(new.splitlines()))
            seen, kept = set(), []
            for row in rows:
                if tuple(row) not in seen:
                    seen.add(tuple(row))
                    kept.append(row)
            with path.open("w", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(kept)
            continue
        if new != text:
            path.write_text(new)


def apply(pairs, root=REPO):
    moved = mapping(pairs)
    facts = read_facts(Path(root) / "facts")
    by_id = {f["id"]: f for f in facts}
    for drop, keep in sorted(moved.items(), key=lambda kv: kv[1]):
        by_id[keep] = merged(by_id[keep], by_id[drop])
    write_facts([by_id[f["id"]] for f in facts if f["id"] not in moved], Path(root) / "facts")
    rewrite_references(moved, root)
    return moved

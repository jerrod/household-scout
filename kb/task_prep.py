import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kb.ingest import read_mail_text  # noqa: E402
from kb.sources.mail import save_mail  # noqa: E402


from kb.sources.mail import MAIL  # noqa: E402

FIND = """select m.ROWID, s.subject, a.address, a.comment from messages m left join subjects s on s.ROWID = m.subject
left join addresses a on a.ROWID = m.sender where m.deleted = 0 and m.date_received between ? and ?"""


def matches(date, entity, mail=MAIL):
    import datetime
    import re
    day = datetime.datetime.fromisoformat(date).timestamp()
    words = [w for w in re.findall(r"[a-z0-9]+", (entity or "").lower()) if len(w) >= 4 and w not in ("services", "health", "credit", "card", "savings", "bank")]
    if not words:
        return []
    con = sqlite3.connect(f"file:{mail}/MailData/Envelope Index?mode=ro", uri=True)
    found = []
    for rowid, subject, address, name in con.execute(FIND, (day - 86400, day + 2 * 86400)):
        text = f"{subject or ''} {address or ''} {name or ''}".lower()
        if any(word in text for word in words):
            found.append(rowid)
    return found[:3]


def prepare(query, out, index=REPO / ".kb/kb.sqlite"):
    con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for fact, source in con.execute(query):
        mails = []
        date, entity = con.execute("select date, entity from facts where id = ?", (fact,)).fetchone()
        if any(ref.startswith("mail:") for ref in source.split()):
            for rowid in matches(date, entity):
                folder = out / "mail" / str(rowid)
                eml, files = save_mail(rowid, folder)
                if eml:
                    (folder / "body.txt").write_text(read_mail_text(eml))
                mails.append({"id": rowid, "saved": eml, "files": files})
        rows.append({"fact": fact, "source": source, "mails": mails})
    with open(out / "facts.jsonl", "w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save the mail behind a set of facts so a headless review can read it")
    parser.add_argument("name")
    parser.add_argument("query", help="SQL returning fact id and source")
    args = parser.parse_args()
    print(prepare(args.query, REPO / "inbox" / f"task-{args.name}"), "facts prepared")

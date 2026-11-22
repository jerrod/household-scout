import sqlite3
from pathlib import Path

from kb.sources.notes import stamp

STORES = Path.home() / "Library/Group Containers/group.com.apple.reminders/Container_v1/Stores"
QUERY = """
select r.ZCKIDENTIFIER, l.ZNAME, r.ZTITLE, r.ZNOTES, r.ZCOMPLETED, r.ZDUEDATE, r.ZCREATIONDATE, r.ZLASTMODIFIEDDATE, r.ZCOMPLETIONDATE
from ZREMCDREMINDER r left join ZREMCDBASELIST l on l.Z_PK = r.ZLIST
where (r.ZMARKEDFORDELETION = 0 or r.ZMARKEDFORDELETION is null)
"""


def read_all(stores=STORES):
    rows = []
    for database in sorted(Path(stores).glob("Data-*.sqlite")):
        con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        for ident, name, title, notes, done, due, made, changed, finished in con.execute(QUERY):
            rows.append({"id": ident or "", "list": name or "", "title": title or "", "body": notes or "", "completed": bool(done),
                         "due": stamp(due), "created": stamp(made), "modified": stamp(changed or made), "completed_at": stamp(finished)})
    return rows


def collect(since, stores=STORES):
    rows = [row for row in read_all(stores) if row["modified"] > since]
    return rows, max([row["modified"] for row in rows], default=since)

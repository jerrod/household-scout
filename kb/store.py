import csv
import json
import sqlite3
from pathlib import Path

from kb import graph
from kb.facts import read_facts
from kb.records import read_records
from kb.schema import DATABASE, ENTITY_FOLDERS, FACT_COLUMNS, PRIVATE_FOLDERS, REPO

DOCUMENT_ROOTS = ["documents/archive", "documents/library", "vault", "secrets"]
NOTE_FILES = ["open-items.md", "emergency.md", "needs-you.md"]
NOTE_FOLDERS = ["expenses", "finance", "games", "inventory", "maintenance", "reminders", "documents"]

SCHEMA = f"""
create table facts ({", ".join(c + (" real" if c == "amount" else " text") for c in FACT_COLUMNS)}, org text default '');
create index facts_date on facts(date);
create index facts_link on facts(link);
create virtual table facts_fts using fts5(summary, entity, contact, kind, value, content='facts', content_rowid='rowid');
create table records (path text primary key, folder text, kind text, name text, updated text, fields text, body text);
create table fields (path text, key text, value text);
create table record_documents (record text, path text);
create table links (source text, relation text, target text);
create virtual table records_fts using fts5(name, body, fields, content='records', content_rowid='rowid');
create table ledger (id text, date text, vendor text, category text, kind text, amount real, summary text, source text);
create table documents (path text primary key, category text, year text, name text, private integer, title text, summary text, source text default '');
create virtual table documents_fts using fts5(name, category, title, summary, content='documents', content_rowid='rowid');
create table notes (path text primary key, title text, body text);
create virtual table notes_fts using fts5(title, body, content='notes', content_rowid='rowid');
create table unread_mail (date text, kind text, sender text, subject text, source text);
"""


def number(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def load_facts(con, repo):
    rows = [[fact[c] if c != "amount" else number(fact[c]) for c in FACT_COLUMNS] for fact in read_facts(repo / "facts")]
    con.executemany(f"insert into facts ({','.join(FACT_COLUMNS)}) values ({','.join('?' * len(FACT_COLUMNS))})", rows)
    con.execute("insert into facts_fts(rowid, summary, entity, contact, kind, value) select rowid, summary, entity, contact, kind, value from facts")


def load_records(con, repo):
    for record in read_records(repo):
        fields = record["fields"]
        con.execute(
            "insert into records values (?,?,?,?,?,?,?)",
            (record["path"], record["folder"], fields.get("type", ""), fields.get("name", ""), fields.get("updated", ""), json.dumps(fields), record["body"]),
        )
        for key, value in fields.items():
            for item in value if isinstance(value, list) else [value]:
                con.execute("insert into fields values (?,?,?)", (record["path"], key, str(item)))
        con.executemany("insert into links values (?,?,?)", [(record["path"], relation, target) for relation, target in record["links"]])
        con.executemany("insert into record_documents values (?,?)", [(record["path"], path) for path in record["documents"]])
    con.execute("insert into records_fts(rowid, name, body, fields) select rowid, name, body, fields from records")


def load_ledger(con, repo):
    with (repo / "expenses/ledger.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            source = f"mail:{row['mail_id']}" if row["mail_id"] else ""
            con.execute("insert into ledger values (?,?,?,?,?,?,?,?)", (row["id"], row["date"], row["vendor"], row["category"], row["kind"], number(row["amount"]), row["summary"], source))


def library_summaries(repo):
    index = repo / "documents/library/INDEX.md"
    if not index.exists():
        return
    for line in index.read_text().split("\n"):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("| `") and len(cells) >= 6:
            yield "documents/library/" + cells[0].strip("`"), cells[2], cells[5]


def load_documents(con, repo):
    for root in DOCUMENT_ROOTS:
        for file in sorted((repo / root).rglob("*")):
            if not file.is_file() or file.name in ("INDEX.md", ".DS_Store", ".gitkeep"):
                continue
            parts = file.relative_to(repo / root).parts
            category = parts[0] if len(parts) > 1 else ""
            year = parts[1] if len(parts) > 2 and parts[1].isdigit() else ""
            private = int(root.split("/")[0] in PRIVATE_FOLDERS)
            con.execute("insert into documents values (?,?,?,?,?,'','','')", (str(file.relative_to(repo)), category, year, file.name, private))
    for path, title, summary in library_summaries(repo):
        con.execute("update documents set title = ?, summary = ? where path = ?", (title, summary, path))
    con.execute("insert into documents_fts(rowid, name, category, title, summary) select rowid, name, category, title, summary from documents")


def load_notes(con, repo):
    files = [repo / name for name in NOTE_FILES]
    for folder in NOTE_FOLDERS:
        files += sorted((repo / folder).glob("*.md"))
    for file in files:
        if file.exists():
            text = file.read_text()
            title = next((line.lstrip("# ").strip() for line in text.split("\n") if line.startswith("# ")), file.stem)
            con.execute("insert into notes values (?,?,?)", (str(file.relative_to(repo))[:-3], title, text))
    con.execute("insert into notes_fts(rowid, title, body) select rowid, title, body from notes")


def load_unread(con, repo):
    path = repo / "unread/invites-and-tickets.csv"
    if path.exists():
        with path.open(newline="") as handle:
            con.executemany("insert into unread_mail values (?,?,?,?,?)", [tuple(row.values()) for row in csv.DictReader(handle)])


def build(repo=REPO, database=DATABASE):
    database.parent.mkdir(parents=True, exist_ok=True)
    database.unlink(missing_ok=True)
    con = sqlite3.connect(database)
    con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    for load in (load_facts, load_records, load_ledger, load_documents, load_notes, load_unread, graph.load_orgs, graph.load_document_sources, graph.load_document_notes):
        load(con, repo)
    links = con.execute("select source, relation, target from links").fetchall()
    graph.build_edges(con, [tuple(row) for row in links], [tuple(row) for row in con.execute("select record, path from record_documents")])
    con.commit()
    return con


def newest_source(repo=REPO):
    folders = ["facts", "expenses", "unread", "organizations", *NOTE_FOLDERS, *ENTITY_FOLDERS]
    files = [file for folder in folders for file in (repo / folder).glob("*") if file.is_file()]
    files += list(Path(__file__).parent.glob("*.py"))
    times = [file.stat().st_mtime for file in files]
    return max(times, default=0)


def connect(repo=REPO, database=DATABASE):
    if not database.exists() or database.stat().st_mtime < newest_source(repo):
        build(repo, database).close()
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con

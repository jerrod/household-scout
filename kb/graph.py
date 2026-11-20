import csv
import re

from kb.schema import ENTITY_FOLDERS

EDGES = "create table edges (source text, relation text, target text); create index edges_source on edges(source); create index edges_target on edges(target);"
ORGS = """
create table orgs (id text primary key, name text, kind text, record text);
create table org_names (name text primary key, org text, unit text);
create virtual table orgs_fts using fts5(name, kind, content='orgs', content_rowid='rowid');
"""


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_orgs(con, repo):
    con.executescript(ORGS)
    for row in read_csv(repo / "organizations/organizations.csv"):
        con.execute("insert into orgs values (?,?,?,?)", (row["id"], row["name"], row["kind"], row["record"]))
    for row in read_csv(repo / "organizations/names.csv"):
        con.execute("insert or replace into org_names values (?,?,?)", (row["name"], row["org"], row["unit"]))
    con.execute("insert into orgs_fts(rowid, name, kind) select rowid, name, kind from orgs")
    con.execute("update facts set org = coalesce((select org from org_names where org_names.name = facts.entity), '')")
    con.execute("update facts set org = coalesce((select id from orgs where orgs.record = facts.link), org) where link != ''")


def load_document_notes(con, repo):
    for row in read_csv(repo / "documents/summaries.csv"):
        con.execute("update documents set title = ?, summary = ? where path = ?", (row["title"], row["summary"], row["path"]))
    con.execute("insert into documents_fts(documents_fts) values ('rebuild')")
    con.execute("create table fact_documents (fact text, path text)")
    con.executemany("insert into fact_documents values (?,?)", [(row["fact"], row["path"]) for row in read_csv(repo / "documents/fact-links.csv")])


def load_document_sources(con, repo):
    for row in read_csv(repo / "documents/sources.csv"):
        changed = con.execute("update documents set source = ? where path = ?", (row["source"], row["path"])).rowcount
        if not changed:
            con.execute("insert into fields values ('documents/sources', 'missing_document_source', ?)", (row["path"],))


def person_paths(con):
    paths = {}
    for row in con.execute("select path, fields from records where folder = 'people'"):
        match = re.search(r'"fact_name": "([^"]+)"', row["fields"])
        if match:
            paths[match.group(1)] = row["path"]
    return paths


def source_parts(source):
    return [] if source.startswith("calendar:") else [part for part in source.split(" ") if part.startswith("mail:")]


def build_edges(con, record_links, record_documents):
    con.executescript(EDGES)
    add = lambda rows: con.executemany("insert into edges values (?,?,?)", rows)
    add((source, relation, target) for source, relation, target in record_links)
    add((source, "document", path) for source, path in record_documents)
    people = person_paths(con)
    by_source = {}
    for row in con.execute("select path, source from documents where source like 'mail:%'"):
        by_source.setdefault(row["source"], []).append(row["path"])
    payments = {}
    for row in con.execute("select id, source from ledger where source != ''"):
        payments.setdefault(row["source"], []).append(row["id"])
    rows = []
    for fact in con.execute("select id, person, org, link, source from facts"):
        if fact["person"] in people:
            rows.append((fact["id"], "about", people[fact["person"]]))
        if fact["org"]:
            rows.append((fact["id"], "with", "org:" + fact["org"]))
        if fact["link"]:
            rows.append((fact["id"], "concerns", fact["link"]))
        for part in source_parts(fact["source"]):
            rows += [(fact["id"], "evidence", path) for path in by_source.get(part, [])]
            rows += [(fact["id"], "payment", payment) for payment in payments.get(part, [])]
    add(rows)
    add((row["fact"], "evidence", row["path"]) for row in con.execute("select fact, path from fact_documents where path in (select path from documents)").fetchall())
    add((row["id"], "paid_to", row["record"]) for row in con.execute("select l.id, r.path as record from ledger l join records r on r.name = l.vendor and r.folder = 'vendors'"))
    add((row["id"], "evidence", path) for row in con.execute("select id, source from ledger where source != ''").fetchall() for path in by_source.get(row["source"], []))
    add(("org:" + row["id"], "same_as", row["record"]) for row in con.execute("select id, record from orgs where record != ''"))


def is_record(node):
    return node.split("/")[0] in ENTITY_FOLDERS

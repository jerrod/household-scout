import json

from kb.schema import DOMAINS, ENTITY_FOLDERS, PEOPLE

ERRORS = [
    "fact id used twice",
    "fact date is not YYYY-MM-DD",
    "fact person is not a known person",
    "fact domain is not a known domain",
    "fact links to a missing record",
    "fact appears twice",
    "record lacks type, name or updated",
    "record type does not match its folder",
    "record links to a missing record",
    "record names a missing document",
    "name maps to a missing organization",
    "organization points to a missing record",
    "document source names a missing file",
    "fact link names a missing document or fact",
]
WARNINGS = [
    "fact has no source",
    "fact has no person",
    "fact summary is cut at 120 characters",
    "fact entity is cut at 40 characters",
    "entity name has no organization entry",
    "document has no title from a reader",
]


def column(con, statement, values=()):
    return [" ".join(str(value) for value in row) for row in con.execute(statement, values)]


def marks(items):
    return ",".join("?" * len(items))


def fact_errors(con):
    return {
        "fact id used twice": column(con, "select id from facts group by id having count(*) > 1"),
        "fact date is not YYYY-MM-DD": column(con, "select id, date from facts where date not glob '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'"),
        "fact person is not a known person": column(con, f"select id, person from facts where person not in ({marks(PEOPLE)})", PEOPLE),
        "fact domain is not a known domain": column(con, f"select id, domain from facts where domain not in ({marks(DOMAINS)})", DOMAINS),
        "fact links to a missing record": column(con, "select id, link from facts where link != '' and link not in (select path from records) and link not in (select path from notes)"),
        "fact appears twice": column(con, "select min(id), max(id), summary from facts group by date, time, person, domain, summary, source having count(*) > 1"),
    }


def record_errors(con):
    missing, mismatch = [], []
    for row in con.execute("select path, folder, fields from records"):
        fields = json.loads(row["fields"])
        if not all(fields.get(key) for key in ("type", "name", "updated")):
            missing.append(row["path"])
        elif fields["type"] != ENTITY_FOLDERS[row["folder"]]:
            mismatch.append(f"{row['path']} type {fields['type']}")
    return {
        "record lacks type, name or updated": missing,
        "record type does not match its folder": mismatch,
        "record links to a missing record": column(con, "select source, target from links where target not in (select path from records)"),
        "record names a missing document": column(con, "select record, path from record_documents where path not in (select path from documents)"),
        "name maps to a missing organization": column(con, "select name, org from org_names where org != '' and org not in (select id from orgs)"),
        "organization points to a missing record": column(con, "select id, record from orgs where record != '' and record not in (select path from records)"),
        "document source names a missing file": column(con, "select value from fields where key = 'missing_document_source'"),
        "fact link names a missing document or fact": column(con, "select fact, path from fact_documents where path not in (select path from documents) or fact not in (select id from facts)"),
    }


def warnings(con):
    return {
        "fact has no source": column(con, "select id, domain, summary from facts where source = ''"),
        "fact has no person": column(con, "select id, domain, summary from facts where person = ''"),
        "fact summary is cut at 120 characters": column(con, "select id, summary from facts where length(summary) = 120 and summary not glob '*[.!?)]'"),
        "fact entity is cut at 40 characters": column(con, "select id, entity from facts where length(entity) = 40"),
        "document has no title from a reader": column(con, "select path from documents where title = '' and (path like 'documents/archive/%' or path like 'vault/archive/%')"),
        "entity name has no organization entry": column(con, "select entity, count(*) from facts where entity != '' and entity not in (select name from org_names) group by 1 order by 2 desc"),
    }


def run(con):
    found = {**fact_errors(con), **record_errors(con), **warnings(con)}
    return {name: found[name] for name in ERRORS + WARNINGS}

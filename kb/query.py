import json
import re

FILTERS = {"org": "org = ?", "person": "person = ?", "domain": "domain = ?", "kind": "kind = ?", "since": "date >= ?", "until": "date <= ?", "link": "link = ?"}
SEARCHED = {
    "records": ("records_fts", "records", "path as ref, name as title, kind as detail"),
    "documents": ("documents_fts", "documents", "path as ref, coalesce(nullif(title, ''), name) as title, category as detail"),
    "notes": ("notes_fts", "notes", "path as ref, title, '' as detail"),
}


def match_text(text):
    terms = re.findall(r"[\w'.@-]+", text)
    return " ".join('"%s"*' % term.replace('"', "") for term in terms)


def facts(con, text="", limit=50, newest_first=True, **filters):
    where, values = [], []
    if text:
        where.append("rowid in (select rowid from facts_fts where facts_fts match ?)")
        values.append(match_text(text))
    for key, value in filters.items():
        if value:
            where.append(FILTERS[key])
            values.append(value)
    clause = "where " + " and ".join(where) if where else ""
    order = "desc" if newest_first else "asc"
    return [dict(row) for row in con.execute(f"select * from facts {clause} order by date {order}, time {order} limit ?", (*values, limit))]


def count_facts(con, text="", **filters):
    where, values = [], []
    if text:
        where.append("rowid in (select rowid from facts_fts where facts_fts match ?)")
        values.append(match_text(text))
    for key, value in filters.items():
        if value:
            where.append(FILTERS[key])
            values.append(value)
    clause = "where " + " and ".join(where) if where else ""
    return con.execute(f"select count(*) from facts {clause}", values).fetchone()[0]


def search(con, text, limit=10, private=False):
    found = {"facts": facts(con, text, limit=limit)}
    for name, (index, table, columns) in SEARCHED.items():
        guard = "" if private or table != "documents" else " and private = 0"
        rows = con.execute(f"select {columns} from {table} where rowid in (select rowid from {index} where {index} match ?){guard} limit ?", (match_text(text), limit))
        found[name] = [dict(row) for row in rows]
    found["organizations"] = [dict(row) for row in con.execute("select id as ref, name as title, kind as detail from orgs where rowid in (select rowid from orgs_fts where orgs_fts match ?) limit ?", (match_text(text), limit))]
    like = f"%{text}%"
    found["ledger"] = [dict(row) for row in con.execute("select * from ledger where vendor like ? or summary like ? order by date desc limit ?", (like, like, limit))]
    found["unread_mail"] = [dict(row) for row in con.execute("select * from unread_mail where subject like ? or sender like ? order by date desc limit ?", (like, like, limit))]
    return found


def resolve(con, name):
    exact = con.execute("select path from records where path = ? or path like ?", (name, f"%/{name}")).fetchall()
    if len(exact) == 1:
        return exact[0]["path"]
    rows = con.execute("select path from records where rowid in (select rowid from records_fts where records_fts match ?) limit 20", ("name: " + match_text(name),)).fetchall()
    if len(rows) == 1:
        return rows[0]["path"]
    raise LookupError(f"{name!r} matches {[row['path'] for row in list(exact) + list(rows)] or 'no record'}")


def show(con, name, limit=200):
    path = resolve(con, name)
    record = dict(con.execute("select * from records where path = ?", (path,)).fetchone())
    record["fields"] = json.loads(record["fields"])
    record["links_to"] = [f"{row['relation']}: {row['target']}" for row in con.execute("select relation, target from links where source = ? order by relation, target", (path,))]
    record["linked_from"] = [f"{row['relation']}: {row['source']}" for row in con.execute("select relation, source from links where target = ? order by relation, source", (path,))]
    record["documents"] = [row["path"] for row in con.execute("select path from record_documents where record = ? order by path", (path,))]
    fact_name = record["fields"].get("fact_name")
    record["facts"] = facts(con, person=fact_name, limit=limit) if fact_name else facts(con, link=path, limit=limit)
    record["ledger"] = [dict(row) for row in con.execute("select * from ledger where vendor = ? order by date desc", (record["name"],))]
    return record


def fact(con, fact_id):
    row = con.execute("select * from facts where id = ?", (fact_id.upper(),)).fetchone()
    if not row:
        raise LookupError(f"no fact {fact_id}")
    return dict(row)


def listing(con, folder, keys):
    rows = []
    for row in con.execute("select path, fields from records where folder = ? order by path", (folder,)):
        fields = json.loads(row["fields"])
        values = {key: ", ".join(fields[key]) if isinstance(fields.get(key), list) else fields.get(key, "") for key in keys}
        rows.append({"path": row["path"], **values})
    return rows


def find_org(con, name):
    rows = con.execute("select * from orgs where id = ? or lower(name) = lower(?)", (name, name)).fetchall()
    if not rows:
        rows = con.execute("select * from orgs where rowid in (select rowid from orgs_fts where orgs_fts match ?) limit 20", ("name: " + match_text(name),)).fetchall()
    if len(rows) != 1:
        raise LookupError(f"{name!r} matches {[row['name'] for row in rows] or 'no organization'}")
    return dict(rows[0])


def org(con, name, limit=200):
    found = find_org(con, name)
    found["names"] = [dict(row) for row in con.execute("select name, unit, (select count(*) from facts where entity = org_names.name) as facts from org_names where org = ? order by 3 desc", (found["id"],))]
    found["facts"] = facts(con, org=found["id"], limit=limit)
    found["fact_count"] = count_facts(con, org=found["id"])
    found["people"] = {row[0]: row[1] for row in con.execute("select person, count(*) from facts where org = ? group by 1 order by 2 desc", (found["id"],))}
    found["documents"] = [row[0] for row in con.execute("select distinct e.target from edges e join facts f on f.id = e.source where f.org = ? and e.relation = 'evidence' order by 1", (found["id"],))]
    return found


def neighbors(con, node):
    out = [dict(row) for row in con.execute("select relation, target as node, count(*) as n from edges where source = ? group by 1, 2 order by 1, 2", (node,))]
    back = [dict(row) for row in con.execute("select relation, case when source glob 'F[0-9]*' then 'facts' when source glob 'P[0-9]*' then 'payments' else source end as node, count(*) as n from edges where target = ? group by 1, 2 order by 1, 2", (node,))]
    return {"node": node, "out": out, "in": back}


def run_sql(con, statement):
    cursor = con.execute(statement)
    return [dict(row) for row in cursor.fetchmany(5000)]


def stats(con):
    by = lambda column: {row[0]: row[1] for row in con.execute(f"select {column}, count(*) from facts group by 1 order by 2 desc")}
    tables = {name: con.execute(f"select count(*) from {name}").fetchone()[0] for name in ("facts", "records", "orgs", "edges", "ledger", "documents", "notes", "unread_mail")}
    span = con.execute("select min(date), max(date) from facts where date glob '[12][0-9][0-9][0-9]-*'").fetchone()
    return {"tables": tables, "first": span[0], "last": span[1], "domain": by("domain"), "person": by("person"), "records": {row[0]: row[1] for row in con.execute("select folder, count(*) from records group by 1")}}

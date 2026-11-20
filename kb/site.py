import datetime
import json
from pathlib import Path

from kb import household, store

TEMPLATE = Path(__file__).parent / "site_template.html"
FACT_FIELDS = ("id", "date", "time", "entity", "summary", "value", "amount", "contact", "link", "source")
CODED = ("person", "domain", "kind")


def codes(con, column):
    return [row[0] for row in con.execute(f"select {column} from facts group by 1 order by count(*) desc")]


def org_rows(con):
    return [list(row) for row in con.execute("select o.id, o.name, o.kind, o.record, (select count(*) from facts f where f.org = o.id) from orgs o order by 5 desc, 2")]


def fact_rows(con, tables, orgs):
    index = {column: {value: n for n, value in enumerate(tables[column])} for column in CODED}
    org_index = {row[0]: n for n, row in enumerate(orgs)}
    rows = []
    for fact in con.execute("select * from facts order by date desc, time desc"):
        rows.append([fact[field] for field in FACT_FIELDS] + [index[column][fact[column]] for column in CODED] + [org_index.get(fact["org"], -1)])
    return rows


def record_rows(con):
    rows = []
    for record in con.execute("select * from records order by folder, name"):
        path = record["path"]
        rows.append(
            {
                "p": path,
                "f": record["folder"],
                "n": record["name"],
                "k": json.loads(record["fields"]),
                "b": record["body"],
                "to": [list(row) for row in con.execute("select relation, target from links where source = ? order by 1, 2", (path,))],
                "from": [list(row) for row in con.execute("select relation, source from links where target = ? order by 1, 2", (path,))],
                "docs": [row[0] for row in con.execute("select d.path from record_documents r join documents d on d.path = r.path where r.record = ? and d.private = 0 order by 1", (path,))],
            }
        )
    return rows


def site_data(con, today=None):
    tables = {column: codes(con, column) for column in CODED}
    orgs = org_rows(con)
    names = {}
    for row in con.execute("select org, name from org_names where org != '' order by name"):
        names.setdefault(row["org"], []).append(row["name"])
    return {
        "orgs": orgs,
        "org_names": names,
        "built": today or datetime.date.today().isoformat(),
        **tables,
        "facts": fact_rows(con, tables, orgs),
        "records": record_rows(con),
        "ledger": [list(row) for row in con.execute("select date, vendor, category, kind, amount, summary, source from ledger order by date desc")],
        "docs": [list(row) for row in con.execute("select path, category, year, coalesce(nullif(title, ''), name), summary from documents where private = 0 order by path")],
        "notes": [{"p": row["path"], "t": row["title"], "b": row["body"]} for row in con.execute("select * from notes order by path")],
        "unread": con.execute("select count(*) from unread_mail").fetchone()[0],
    }


def build_site(out, con=None):
    con = con or store.connect()
    payload = json.dumps(site_data(con), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    Path(out).write_text(TEMPLATE.read_text().replace("/*DATA*/null", payload).replace("/*NAME*/", household.NAME).replace("/*FAMILY*/[]", json.dumps(household.FAMILY + household.PETS)))
    return Path(out).stat().st_size

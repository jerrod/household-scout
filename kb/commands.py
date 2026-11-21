import json
import sys

from kb import check, edit, query, site, store
from kb.render import fact_line, neighbors_text, org_text, record_text, row_line, source_text
from kb.household import KIDS
from kb.sources import calendar, mail, texts

FILTER_KEYS = ("person", "domain", "kind", "org", "since", "until")


def emit(args, data, text):
    print(json.dumps(data, indent=1) if args.json else text)


def facts(con, args):
    text = " ".join(args.text)
    filters = {key: getattr(args, key) for key in FILTER_KEYS}
    rows = query.facts(con, text, limit=args.limit, newest_first=not args.oldest, **filters)
    total = query.count_facts(con, text, **filters)
    tail = f"\n-- {len(rows)} of {total} shown. Raise --limit or narrow the filters." if total > len(rows) else ""
    emit(args, rows, "\n".join(fact_line(row) for row in rows) + tail)


def find(con, args):
    found = query.search(con, " ".join(args.text), limit=args.limit, private=args.private)
    lines = []
    for section, rows in found.items():
        if rows:
            lines.append(f"## {section}")
            lines += [fact_line(row) if section == "facts" else "  " + row_line(row) for row in rows]
    emit(args, found, "\n".join(lines) or "nothing found")


def show(con, args):
    record = query.show(con, " ".join(args.name))
    emit(args, record, record_text(record))


def org(con, args):
    found = query.org(con, " ".join(args.name), limit=args.limit)
    emit(args, found, org_text(found))


def links(con, args):
    name = " ".join(args.name)
    try:
        node = query.resolve(con, name)
    except LookupError:
        node = "org:" + query.find_org(con, name)["id"]
    found = query.neighbors(con, node)
    emit(args, found, neighbors_text(found))


def listing(con, args):
    rows = query.listing(con, args.folder, args.fields.split(","))
    emit(args, rows, "\n".join(row_line(row) for row in rows))


def source(con, args):
    fact = query.fact(con, args.id)
    found = []
    for part in fact["source"].split(" ") if not fact["source"].startswith("calendar:") else [fact["source"]]:
        kind, _, ref = part.partition(":")
        if kind == "mail":
            found.append({"source": part, "mail": mail.read_mail(int(ref), limit=args.limit)})
        elif kind in ("window", "text"):
            start = texts.window_start(ref) if kind == "window" else int(ref)
            found.append({"source": part, "thread": texts.read_thread(start) if start else []})
        else:
            found.append({"source": part, "note": "read this source in its own app"})
    emit(args, {"fact": fact, "sources": found}, fact_line(fact) + "\n" + source_text(found))


def events(con, args):
    rows = [event for event in calendar.read_events() if event["date"] >= args.since]
    emit(args, rows, "\n".join(row_line(row) for row in rows))


def sql(con, args):
    rows = query.run_sql(con, args.statement)
    emit(args, rows, "\n".join(row_line(row) for row in rows))


def audit(con, args):
    from kb.facts import read_facts
    from kb.fact_audit import disagreements
    facts = [f for f in read_facts() if f["date"] >= args.since and not f["value"].startswith("repeats on ")]
    found = [d for d in disagreements(facts) if not args.field or d["field"] == args.field]
    lines = [f"{d['id']}  {d['field']}: {d['has']} -> {d['jev']} ({d['confidence']:.2f})  {d['summary'][:90]}" for d in found]
    emit(args, found, "\n".join(lines) or "no disagreements")


def dupes(con, args):
    from kb import dupes as merge
    from kb.facts import read_facts
    found = merge.find(read_facts())
    lines = [f"{d['keep']} <- {d['drop']}  ({d['score']:.2f})  {d['a'][:70]} | {d['b'][:70]}" for d in found]
    if args.apply:
        moved = merge.apply(found)
        lines.append(f"merged {len(moved)} facts")
    emit(args, found, "\n".join(lines) or "no duplicates")


def stats(con, args):
    print(json.dumps(query.stats(con), indent=1))


def checks(con, args):
    found = check.run(con)
    for name, rows in found.items():
        print(f"{len(rows):6d}  {'error  ' if name in check.ERRORS else 'warning'}  {name}")
        for row in rows[: args.examples]:
            print(f"                 {row}")
    if any(found[name] for name in check.ERRORS):
        sys.exit(1)


def add(con, args):
    rows = [json.loads(line) for line in sys.stdin if line.strip()]
    added, skipped = edit.add_facts(rows)
    print(f"added {len(added)} facts, skipped {len(skipped)} already present")
    for fact in added:
        print(fact["id"], fact["date"], fact["summary"])


def mail_command(con, args):
    from pathlib import Path
    from kb.sources import mail as mailbox
    if args.save:
        eml, attachments = mailbox.save_mail(args.id, Path(args.save))
        print(json.dumps({"eml": eml, "attachments": attachments}, indent=1))
    else:
        found = mailbox.read_mail(args.id, limit=args.limit)
        print(json.dumps(found, indent=1, default=str) if args.json else f"{found.get('sender')} | {found.get('subject')}\n{found.get('body')}\nattachments: {found.get('attachments')}")


def intake(con, args):
    from kb import intake as queue
    if args.action == "pull":
        folder, items = queue.pull(args.day)
        print(f"{len(items)} waiting items in {folder}")
        for item in items:
            print(item["id"], item["kind"], item.get("submitted_by", ""), item.get("filename") or item["fact"].get("summary", ""))
    else:
        print(json.dumps(queue.resolve(args.id, args.action, args.outcome)))


def build(con, args):
    store.build().close()
    print("built", store.DATABASE)


def publish(con, args):
    size = site.build_site(args.out, con)
    print(f"wrote {args.out}, {size / 1e6:.1f} MB")


OUTINGS = ("practice", "game", "appointment", "event", "lesson", "vehicle", "medical", "dental", "activity", "camp", "trip", "test")


def week(con, args):
    import datetime
    start = datetime.date.fromisoformat(args.start) if args.start else datetime.date.today()
    end = start + datetime.timedelta(days=args.days - 1)
    from kb.recurring import PREFIX, DATES
    found = con.execute("""select id, coalesce(nullif(due, ''), date) as day, time, person, kind, entity, summary, value from facts
        where (coalesce(nullif(due, ''), date) between ? and ? or value like ?) and domain != 'job' and kind not in ('grade', 'attendance', 'policy', 'contact')
        and summary not like '%(copy)'""", (start.isoformat(), end.isoformat(), PREFIX + "%")).fetchall()
    rows = []
    for code, day, time, person, kind, entity, summary, value in found:
        for when in (DATES.findall(value.split(":", 1)[1]) if value.startswith(PREFIX) else [day]):
            if start.isoformat() <= when <= end.isoformat():
                rows.append((code, when, time, person, kind, entity, summary))
    rows.sort(key=lambda r: (r[1], r[2] == "", r[2], r[3] or ""))
    days = {}
    for code, day, time, person, kind, entity, summary in rows:
        if args.person and person != args.person:
            continue
        ride = person in KIDS and kind in OUTINGS and "school" not in (entity or "").lower()
        days.setdefault(day, []).append({"id": code, "time": time, "person": person or "household", "kind": kind, "where": entity, "summary": summary, "needs_driver": ride})
    lines = []
    for day, items in days.items():
        lines.append(datetime.date.fromisoformat(day).strftime("## %a %b %-d"))
        lines += [f"  {item['time'] or 'all day':>7}  {item['person']:<9} {item['summary']}{'  [needs a driver]' if item['needs_driver'] else ''}  ({item['id']})" for item in items]
    emit(args, days, "\n".join(lines) or "nothing scheduled")

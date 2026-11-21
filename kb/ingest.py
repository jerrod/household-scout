#!/usr/bin/env python3
"""Collect everything new since the last run: mail, texts, calendar events and Documents files.

Writes inbox/<date>/ with one JSONL file per source, then classifies the new mail with Jev.
State lives in .kb-state.json. Pass --commit-state to advance the watermarks after a successful run.
"""
import argparse
import datetime
import email
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from email import policy
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
STATE = REPO / f".kb-state.{os.uname().nodename.split('.')[0]}.json"
HOME = Path.home()
MAIL = HOME / "Library/Mail/V10"
CHAT = HOME / "Library/Messages/chat.db"
CAL = HOME / "Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb"
DOCS = HOME / "Documents"
from kb import household  # noqa: E402

SKIP_DIRS = {"node_modules", ".venv", "venv", "site-packages", ".git", "dist", "build", "__pycache__"} | set(household.source("documents").get("skip", []))
EPOCH = 978307200


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def mail_body(path):
    raw = Path(path).read_bytes()
    count = int(raw[: raw.index(b"\n")])
    msg = email.message_from_bytes(raw[raw.index(b"\n") + 1 : raw.index(b"\n") + 1 + count], policy=policy.default)
    for kind in ("text/plain", "text/html"):
        for part in msg.walk():
            if part.get_content_type() == kind and not part.is_attachment():
                text = part.get_content()
                if kind == "text/html":
                    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(style|script).*?</\1>", " ", text)))
                if squash(text):
                    return squash(text)[:800], [p.get_filename() for p in msg.walk() if p.get_filename()]
    return "", [p.get_filename() for p in msg.walk() if p.get_filename()]


def emlx_index():
    paths = {}
    for p in MAIL.glob("*/**/*.emlx"):
        paths[p.name.split(".")[0]] = str(p)
    return paths


def read_mail_text(path):
    message = email.message_from_bytes(Path(path).read_bytes(), policy=policy.default)
    body = message.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    if body and body.get_content_type() == "text/html":
        text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(style|script).*?</\1>", " ", text)))
    return f"From: {message['from']}\nTo: {message['to']}\nDate: {message['date']}\nSubject: {message['subject']}\n\n{squash(text)}\n"


def new_mail(since, not_before=0):
    con = ro(MAIL / "MailData/Envelope Index")
    rows = con.execute(
        """select m.ROWID, m.date_received, a.address, a.comment, s.subject from messages m
           left join addresses a on a.ROWID=m.sender left join subjects s on s.ROWID=m.subject
           where m.deleted=0 and m.ROWID>? and m.date_received>=? order by m.ROWID""",
        (since, not_before),
    ).fetchall()
    paths = emlx_index()
    out = []
    for rid, date, addr, name, subject in rows:
        body, names = ("", [])
        if str(rid) in paths:
            try:
                body, names = mail_body(paths[str(rid)])
            except Exception:
                pass
        out.append({"id": rid, "date": date, "sender": f"{name or ''} <{addr or '?'}>", "subject": subject or "", "snippet": body, "attachments": names})
    return out, max([r["id"] for r in out], default=since)


def new_texts(since, not_before=0):
    con = ro(CHAT)
    out = []
    for rid, date, me, handle, text in con.execute(
        "select m.ROWID, m.date, m.is_from_me, coalesce(h.id,''), m.text from message m left join handle h on h.ROWID=m.handle_id where m.ROWID>? and m.date>=? order by m.ROWID",
        (since, (not_before - EPOCH) * 1e9),
    ):
        if text:
            out.append({"id": rid, "date": date / 1e9 + EPOCH if date else None, "from_me": me, "handle": handle, "text": text})
    return out, max([r["id"] for r in out], default=since)


def new_events(since):
    con = ro(CAL)
    out = []
    for rid, cal, title, notes, start, end, allday in con.execute(
        """select i.ROWID, c.title, i.summary, i.description, i.start_date, i.end_date, i.all_day from CalendarItem i
           join Calendar c on c.ROWID=i.calendar_id where i.ROWID>? and (i.hidden=0 or i.hidden is null) order by i.ROWID""",
        (since,),
    ):
        if cal and cal.strip() in ("Holidays in United States", "US Holidays"):
            continue
        out.append({"id": rid, "calendar": cal, "title": title, "notes": (notes or "")[:600], "start": datetime.datetime.fromtimestamp(start + EPOCH).strftime("%Y-%m-%d %H:%M") if start else None, "all_day": bool(allday)})
    return out, max([r["id"] for r in out], default=since)


def new_docs(since):
    from kb.doc_text import excerpt
    out = []
    for base, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(".app")]
        for name in files:
            full = os.path.join(base, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            if name.startswith(".") or stat.st_mtime <= since:
                continue
            out.append({"path": os.path.relpath(full, DOCS), "bytes": stat.st_size, "text_excerpt": excerpt(full)})
    return out, datetime.datetime.now().timestamp()


def classify(rows, script):
    if not rows:
        return {}
    feed = "\n".join(json.dumps({"id": r["id"], "sender": r["sender"], "subject": r["subject"], "snippet": r["snippet"]}) for r in rows)
    result = subprocess.run([sys.executable, "-I", str(REPO / "bin" / script)], input=feed, capture_output=True, text=True)
    return {json.loads(l)["id"]: json.loads(l) for l in result.stdout.splitlines() if l.strip()}


def ranked(rows):
    if not rows or not rows[0].get("jev"):
        return ""
    from kb import triage
    c = triage.counts(rows)
    return f" ({c['high']} household-likely, {c['low']} under 0.2)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-state", action="store_true")
    parser.add_argument("--no-jev", action="store_true")
    args = parser.parse_args()
    state = json.loads(STATE.read_text())
    day = datetime.date.today().isoformat()
    inbox = REPO / "inbox" / day
    inbox.mkdir(parents=True, exist_ok=True)
    on = household.SOURCES
    apple_mail = on.get("mail", {}).get("reader") == "apple_mail"
    mail, mail_to = new_mail(state["mail_rowid"], state.get("not_before", 0)) if apple_mail else ([], state.get("mail_rowid", 0))
    texts, text_to = new_texts(state["text_rowid"], state.get("not_before", 0)) if "messages" in on else ([], state.get("text_rowid", 0))
    events, cal_to = new_events(state["cal_rowid"]) if on.get("calendar", {}).get("reader") == "apple_calendar" else ([], state.get("cal_rowid", 0))
    docs, docs_to = new_docs(state["docs_mtime"]) if "documents" in on else ([], state.get("docs_mtime", 0))
    flags = {} if args.no_jev else classify(mail, "jev-classify")
    records = {} if args.no_jev else classify(mail, "jev-transaction")
    if not args.no_jev:
        from kb import doc_area, triage
        texts = triage.tag(texts) if texts else texts
        for row, found in zip(docs, doc_area.triage([{"id": i, "path": d["path"], "ext": os.path.splitext(d["path"])[1], "text": d["text_excerpt"]} for i, d in enumerate(docs)])):
            row.update(area=found["area"], confidence=found["confidence"])
    for name, rows in (("mail", mail), ("texts", texts), ("calendar", events), ("documents", docs)):
        with open(inbox / f"{name}.jsonl", "w") as out:
            for r in rows:
                if name == "mail":
                    r = {**r, "jev": flags.get(r["id"]), "record": records.get(r["id"])}
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
    relevant = [r for r in mail if (flags.get(r["id"]) or {}).get("domain") not in (None, "other")]
    digest = [f"# Inbox {day}", "", "| Source | New items |", "| --- | --- |", f"| Mail | {len(mail)} ({len(relevant)} tagged for the household) |", f"| Texts | {len(texts)}{ranked(texts)} |", f"| Calendar events | {len(events)} |", f"| Files in Documents | {len(docs)} |", "", "Next: run the kb-update skill to extract facts, rebuild the records, commit and push."]
    (inbox / "DIGEST.md").write_text("\n".join(digest) + "\n")
    print("\n".join(digest))
    from kb.sources.mail import save_mail
    for row in mail if apple_mail else []:
        folder = inbox / "mail" / str(row["id"])
        eml, files = save_mail(row["id"], folder)
        if eml:
            full = read_mail_text(eml)
            (folder / "body.txt").write_text(full)
        row.update(saved=eml, files=files)
    if on.get("mail", {}).get("reader") == "gmail":
        from kb.sources import gmail
        gmail_rows, state["gmail"] = gmail.collect(state.get("gmail", {}), inbox / "mail")
        mail += gmail_rows
    with open(inbox / "mail.jsonl", "w") as out:
        for row in mail:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    from kb.sources import canvas
    try:
        if "canvas" not in on:
            raise LookupError("not in household.toml")
        canvas_rows, canvas_to = canvas.collect(state.get("canvas", {}))
        canvas.download_files(canvas_rows, inbox / "canvas")
        known = state.get("canvas_courses", {})
        for snap in canvas.course_snapshots(inbox / "canvas"):
            if known.get(snap["path"].rsplit("/", 1)[-1]) != snap["sha"]:
                canvas_rows.append({"kind": "course", **snap})
            known[snap["path"].rsplit("/", 1)[-1]] = snap["sha"]
        state["canvas_courses"] = known
    except Exception as error:
        canvas_rows, canvas_to = [], state.get("canvas", {})
        print(f"canvas: {error}")
    with open(inbox / "canvas.jsonl", "w") as out:
        for row in canvas_rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    from kb.sources import infinite_campus
    try:
        if "infinite_campus" not in on:
            raise LookupError("not in household.toml")
        campus_rows, campus_seen = infinite_campus.collect(state.get("campus", {}), inbox / "campus")
        state["campus"] = campus_seen
    except Exception as error:
        campus_rows = []
        print(f"infinite campus: {error}")
    with open(inbox / "campus.jsonl", "w") as out:
        for row in campus_rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    from kb.sources import slack
    slack_rows = []
    if slack.LOGIN.exists():
        try:
            slack_rows, state["slack"] = slack.collect(state.get("slack", {}))
        except Exception as error:
            print(f"slack: {error}")
    if slack_rows and not args.no_jev:
        from kb import triage
        slack_rows = triage.tag(slack_rows)
    with open(inbox / "slack.jsonl", "w") as out:
        for row in slack_rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    next_state = {**state, "mail_rowid": mail_to, "text_rowid": text_to, "cal_rowid": cal_to, "docs_mtime": docs_to, "canvas": canvas_to, "last_run": day}
    if slack_rows:
        digest.insert(-2, f"| Slack messages | {len(slack_rows)}{ranked(slack_rows)} |")
        (inbox / "DIGEST.md").write_text("\n".join(digest) + "\n")
    (inbox / "next-state.json").write_text(json.dumps(next_state, indent=2) + "\n")
    if args.commit_state:
        state.update({"mail_rowid": mail_to, "text_rowid": text_to, "cal_rowid": cal_to, "docs_mtime": docs_to, "last_run": day})
        STATE.write_text(json.dumps(state, indent=2) + "\n")


if __name__ == "__main__":
    main()

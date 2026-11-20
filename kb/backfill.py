import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kb.ingest import MAIL, read_mail_text  # noqa: E402
from kb.sources.mail import save_mail  # noqa: E402

QUERY = """select m.ROWID, m.date_received, a.address, a.comment, s.subject from messages m
join mailboxes b on b.ROWID = m.mailbox left join addresses a on a.ROWID = m.sender left join subjects s on s.ROWID = m.subject
where m.deleted = 0 and b.url like ? order by m.date_received"""


def rows(account):
    con = sqlite3.connect(f"file:{MAIL}/MailData/Envelope Index?mode=ro", uri=True)
    return con.execute(QUERY, (f"%{account}%",)).fetchall()


def prepare(account, out, size):
    found = rows(account)
    for start in range(0, len(found), size):
        chunk = out / f"{start // size:03d}"
        if (chunk / "mail.jsonl").exists():
            continue
        chunk.mkdir(parents=True, exist_ok=True)
        with open(chunk / "mail.jsonl", "w") as handle:
            for rid, date, address, name, subject in found[start : start + size]:
                folder = chunk / "mail" / str(rid)
                eml, files = save_mail(rid, folder)
                if eml:
                    (folder / "body.txt").write_text(read_mail_text(eml))
                row = {"id": rid, "date": date, "sender": f"{name or ''} <{address or '?'}>", "subject": subject or "", "saved": eml, "files": files}
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(found)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save every mail of one Mail account into chunked inbox folders for review")
    parser.add_argument("account", help="the account folder id under ~/Library/Mail/V10")
    parser.add_argument("name", help="a short name for the backfill folder")
    parser.add_argument("--size", type=int, default=120)
    args = parser.parse_args()
    out = REPO / "inbox" / f"backfill-{args.name}"
    print(prepare(args.account, out, args.size), "mails in", out)

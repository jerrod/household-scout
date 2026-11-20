import email
import html
import re
import sqlite3
import subprocess
import zipfile
from email import policy
from pathlib import Path

MAIL = Path.home() / "Library/Mail/V10"
HEADER = """select m.date_received, a.address, a.comment, s.subject from messages m
left join addresses a on a.ROWID = m.sender left join subjects s on s.ROWID = m.subject where m.ROWID = ?"""


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def body_text(message):
    body = message.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    text = re.sub(r"(?s)<(style|script).*?</\1>", " ", text)
    return squash(html.unescape(re.sub(r"<[^>]+>", " ", text)))


def find_file(rowid, mail=MAIL):
    return next(iter(mail.glob(f"*/**/{rowid}.emlx")), None) or next(iter(mail.glob(f"*/**/{rowid}.partial.emlx")), None)


def read_mail(rowid, limit=3000, mail=MAIL):
    con = sqlite3.connect(f"file:{mail}/MailData/Envelope Index?mode=ro", uri=True)
    row = con.execute(HEADER, (rowid,)).fetchone()
    if not row:
        return {"id": rowid, "missing": True}
    found = {"id": rowid, "received": row[0], "sender": f"{row[2] or ''} <{row[1] or ''}>".strip(), "subject": row[3] or "", "body": "", "attachments": []}
    path = find_file(rowid, mail)
    if path:
        raw = path.read_bytes()
        cut = raw.index(b"\n")
        message = email.message_from_bytes(raw[cut + 1 : cut + 1 + int(raw[:cut])], policy=policy.default)
        found["body"] = body_text(message)[:limit]
        found["attachments"] = [part.get_filename() for part in message.walk() if part.get_filename()]
    return found


def raw_mail(rowid, mail=MAIL):
    path = find_file(rowid, mail)
    if not path:
        return None
    raw = path.read_bytes()
    cut = raw.index(b"\n")
    return raw[cut + 1 : cut + 1 + int(raw[:cut])]


def save_mail(rowid, folder, mail=MAIL):
    raw = raw_mail(rowid, mail)
    if raw is None:
        return None, []
    folder.mkdir(parents=True, exist_ok=True)
    message = email.message_from_bytes(raw, policy=policy.default)
    saved = []
    stored = {}
    message_file = find_file(rowid, mail)
    for path in (message_file.parent.parent / "Attachments" / str(rowid)).glob("*/*") if message_file else []:
        stored.setdefault(path.name, path)
    for part in message.walk():
        name = part.get_filename()
        if name and not part.is_multipart():
            target = folder / f"{rowid}-{Path(name).name}"
            content = part.get_payload(decode=True) or b""
            if not content and Path(name).name in stored:
                content = stored[Path(name).name].read_bytes()
            target.write_bytes(content)
            saved.append(str(target))
    eml = folder / f"{rowid}.eml"
    eml.write_bytes(raw)
    write_attachment_texts(saved)
    return str(eml), saved


def attachment_text(path):
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
        if suffix in (".docx", ".pptx", ".xlsx"):
            parts = {".docx": r"word/document.xml", ".pptx": r"ppt/slides/slide\d+.xml", ".xlsx": r"xl/sharedStrings.xml"}[suffix]
            with zipfile.ZipFile(path) as archive:
                return html.unescape(" ".join(re.sub(r"<[^>]+>", " ", archive.read(name).decode("utf-8", "replace")) for name in archive.namelist() if re.fullmatch(parts, name)))
        if suffix in (".doc", ".rtf", ".pages", ".ppt", ".xls"):
            return subprocess.run(["textutil", "-convert", "txt", "-stdout", str(path)], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
        if suffix in (".txt", ".csv", ".ics", ".html", ".htm"):
            return path.read_text(errors="replace")
    except (OSError, zipfile.BadZipFile, subprocess.SubprocessError):
        return ""
    return ""


def write_attachment_texts(paths):
    for path in paths:
        text = re.sub(r"[ \t]+", " ", attachment_text(path)).strip()
        if text:
            Path(f"{path}.txt").write_text(text)

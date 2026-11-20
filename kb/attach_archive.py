#!/usr/bin/env python3
"""Archive every household-relevant attachment from Mail and Messages into documents/archive and vault/archive.

Steps: list files, drop duplicates, read text (PDF text, OCR for images and scanned PDFs), classify each file
with Jev, copy the relevant ones. Work files live in .kb-work/attach (ignored by git).
"""
import hashlib, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, zipfile
from multiprocessing import Pool
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORK = REPO / ".kb-work" / ("files" if "--dirs" in sys.argv else "attach")
HOME = Path.home()
DOCS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".rtf", ".pages", ".numbers", ".pptx"}
IMGS = {".jpg", ".jpeg", ".png", ".heic"}
JUNK = re.compile(r"^(image\d+|outlook-|logo|spacer|facebook|twitter|linkedin|instagram|pixel|banner|icon|ATT\d+|mailerprovided|ra_\d|IMG_\d+\.PNG$)", re.I)
KEEP = {"home", "vehicle", "school", "kids", "health", "finance", "legal_id", "pets"}
SENSITIVE = {"health", "legal_id", "finance"}
MAX_BYTES = 25 * 2**20


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return ""


def ocr(path):
    return run(["tesseract", str(path), "-", "--psm", "11"])


def read_text(path):
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        text = run(["pdftotext", "-layout", "-l", "6", path, "-"])
        if len(text.strip()) < 200:
            d = tempfile.mkdtemp()
            run(["pdftoppm", "-r", "150", "-png", "-l", "3", path, d + "/p"])
            text = "\n".join(ocr(os.path.join(d, x)) for x in sorted(os.listdir(d)))
            shutil.rmtree(d, ignore_errors=True)
        return text
    if ext in (".doc", ".docx", ".rtf"):
        return run(["textutil", "-convert", "txt", "-stdout", path])
    if ext == ".xlsx":
        try:
            z = zipfile.ZipFile(path)
            return " | ".join(re.findall(r"<t[^>]*>([^<]*)</t>", z.read("xl/sharedStrings.xml").decode("utf8", "ignore")))
        except Exception:
            return ""
    if ext in (".txt", ".csv"):
        return open(path, errors="ignore").read(6000)
    if ext in IMGS:
        if ext == ".heic":
            tmp = tempfile.mktemp(suffix=".png")
            run(["sips", "-s", "format", "png", path, "--out", tmp])
            text = ocr(tmp) if os.path.exists(tmp) else ""
            if os.path.exists(tmp):
                os.remove(tmp)
            return text
        return ocr(path)
    return ""


def work(item):
    item["text"] = re.sub(r"\s+", " ", read_text(item["path"])).strip()[:900]
    return item


def mail_files():
    env = sqlite3.connect(f"file:{HOME}/Library/Mail/V10/MailData/Envelope Index?mode=ro", uri=True)
    meta = {r[0]: r[1:] for r in env.execute("select m.ROWID, m.date_received, a.address, s.subject from messages m left join addresses a on a.ROWID=m.sender left join subjects s on s.ROWID=m.subject")}
    out = []
    for p in (HOME / "Library/Mail/V10").rglob("Attachments/*/*/*"):
        m = re.search(r"/Attachments/(\d+)/", str(p))
        if m and p.is_file() and not p.name.startswith("."):
            d = meta.get(int(m.group(1)))
            if d:
                out.append({"src": "mail", "id": int(m.group(1)), "path": str(p), "ts": d[0], "sender": d[1] or "", "subject": d[2] or ""})
    return out


def text_files():
    con = sqlite3.connect(f"file:{HOME}/Library/Messages/chat.db?mode=ro", uri=True)
    out = []
    q = "select a.ROWID, a.filename, m.date, coalesce(h.id,''), m.ROWID from attachment a join message_attachment_join j on j.attachment_id=a.ROWID join message m on m.ROWID=j.message_id left join handle h on h.ROWID=m.handle_id where a.filename is not null"
    for aid, fn, date, handle, mid in con.execute(q):
        p = os.path.expanduser(fn)
        if os.path.isfile(p):
            out.append({"src": "text", "id": mid, "path": p, "ts": (date / 1e9 + 978307200) if date else 0, "sender": handle, "subject": "text message"})
    return out


def dir_files(roots):
    out = []
    for root in roots:
        for p in Path(root).expanduser().rglob("*"):
            if p.is_file() and not p.name.startswith(".") and ".photoslibrary/database" not in str(p) and "/derivatives/" not in str(p):
                out.append({"src": "file", "id": 0, "path": str(p), "ts": p.stat().st_mtime, "sender": p.parent.name, "subject": str(p)})
    return out


def date_of(item):
    import datetime
    ts = item["ts"] or 0
    if ts > 1e12:
        ts = ts / 1e9 + 978307200
    return datetime.date.fromtimestamp(ts).isoformat() if ts else "undated"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:30] or "unknown"


def known_hashes():
    seen = set()
    for base in ("documents/archive", "vault/archive"):
        for p in (REPO / base).rglob("*"):
            if p.is_file() and p.name != "INDEX.md":
                seen.add(sha1(p))
    return seen


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    items = dir_files(sys.argv[2:]) if len(sys.argv) > 2 and sys.argv[1] == "--dirs" else mail_files() + text_files()
    print("files found", len(items), flush=True)
    seen = known_hashes()
    keep = []
    for it in items:
        p = Path(it["path"])
        ext = p.suffix.lower()
        size = p.stat().st_size
        if JUNK.match(p.name) or size > MAX_BYTES:
            continue
        if ext in DOCS and size >= 3000 or ext in IMGS and size >= 50000:
            h = sha1(p)
            if h in seen:
                continue
            seen.add(h)
            it["sha"], it["size"] = h, size
            keep.append(it)
    print("after filter and dedupe", len(keep), flush=True)
    with Pool(8) as pool:
        done = pool.map(work, keep, chunksize=8)
    json.dump(done, open(WORK / "items.json", "w"))
    feed = "\n".join(json.dumps({"id": i, "sender": it["sender"], "subject": it["subject"] + " | " + Path(it["path"]).name, "snippet": it["text"]}) for i, it in enumerate(done))
    res = subprocess.run([sys.executable, "-I", str(REPO / "bin" / "jev-classify")], input=feed, capture_output=True, text=True)
    cls = {}
    for line in res.stdout.splitlines():
        if line.strip():
            r = json.loads(line)
            cls[r["id"]] = r
    json.dump(cls, open(WORK / "classes.json", "w"))
    saved = []
    for i, it in enumerate(done):
        c = cls.get(i)
        if not c or c.get("domain") not in KEEP:
            continue
        dom = c["domain"]
        base = "vault/archive" if dom in SENSITIVE else "documents/archive"
        day = date_of(it)
        dest = REPO / base / dom / (day[:4] if day != "undated" else "undated")
        dest.mkdir(parents=True, exist_ok=True)
        name = f"{day}_{slug(it['sender'].split('@')[-1] if it['src'] == 'mail' else it['sender'])}_{re.sub(r'[^A-Za-z0-9._-]+', '-', Path(it['path']).name)[:70]}"
        target = dest / name
        if target.exists():
            target = dest / f"{it['sha'][:6]}_{name}"
        shutil.copy2(it["path"], target)
        saved.append({"src": it["src"], "id": it["id"], "domain": dom, "subtype": c.get("subtype"), "path": str(target.relative_to(REPO)), "bytes": it["size"]})
    json.dump(saved, open(WORK / "saved.json", "w"))
    print("archived", len(saved), sum(s["bytes"] for s in saved) // 2**20, "MB", flush=True)


if __name__ == "__main__":
    main()

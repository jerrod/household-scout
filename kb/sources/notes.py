import datetime
import gzip
import sqlite3
from pathlib import Path

DATABASE = Path.home() / "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
APPLE_EPOCH = 978307200
TRASH = 1
QUERY = """
select o.Z_PK, o.ZTITLE1, f.ZTITLE2, o.ZCREATIONDATE3, o.ZMODIFICATIONDATE1, o.ZISPASSWORDPROTECTED, d.ZDATA
from ZICCLOUDSYNCINGOBJECT o join ZICNOTEDATA d on d.Z_PK = o.ZNOTEDATA
left join ZICCLOUDSYNCINGOBJECT f on f.Z_PK = o.ZFOLDER
where (o.ZMARKEDFORDELETION = 0 or o.ZMARKEDFORDELETION is null) and coalesce(f.ZFOLDERTYPE, 0) != ?
"""


def stamp(seconds):
    return datetime.datetime.fromtimestamp(seconds + APPLE_EPOCH, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") if seconds else ""


def varint(data, at):
    value = shift = 0
    while True:
        byte = data[at]
        value |= (byte & 0x7F) << shift
        at += 1
        if byte < 0x80:
            return value, at
        shift += 7


def field(data, number):
    at = 0
    while at < len(data):
        key, at = varint(data, at)
        kind = key & 7
        if kind == 0:
            _, at = varint(data, at)
        elif kind == 1:
            at += 8
        elif kind == 5:
            at += 4
        elif kind == 2:
            size, at = varint(data, at)
            if key >> 3 == number:
                return data[at:at + size]
            at += size
        else:
            return b""
    return b""


def note_text(blob):
    return field(field(field(gzip.decompress(blob), 2), 3), 2).decode("utf-8", "replace") if blob else ""


def read_all(database=DATABASE):
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    rows = []
    for pk, title, folder, made, changed, locked, blob in con.execute(QUERY, (TRASH,)):
        rows.append({"id": f"p{pk}", "title": title or "", "folder": folder or "", "created": stamp(made), "modified": stamp(changed),
                     "locked": bool(locked), "body": "" if locked else note_text(blob)})
    return rows


def collect(since, database=DATABASE):
    rows = [row for row in read_all(database) if row["modified"] > since]
    return rows, max([row["modified"] for row in rows], default=since)

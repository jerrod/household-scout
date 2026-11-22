import gzip
import sqlite3
import tempfile
import unittest
from pathlib import Path

from kb import ingest, mask
from kb.sources import notes, reminders


def message(number, payload):
    return bytes([number << 3 | 2, len(payload)]) + payload


def note_blob(text):
    return gzip.compress(message(1, b"\x01") + message(2, message(3, b"\x08\x00" + message(2, text.encode()))))


def notes_db(folder):
    path = Path(folder) / "NoteStore.sqlite"
    con = sqlite3.connect(path)
    con.execute("create table ZICCLOUDSYNCINGOBJECT (Z_PK integer, ZTITLE1 text, ZTITLE2 text, ZCREATIONDATE3 real, ZMODIFICATIONDATE1 real, ZISPASSWORDPROTECTED integer, ZNOTEDATA integer, ZFOLDER integer, ZFOLDERTYPE integer, ZMARKEDFORDELETION integer)")
    con.execute("create table ZICNOTEDATA (Z_PK integer, ZDATA blob)")
    con.executemany("insert into ZICCLOUDSYNCINGOBJECT values (?,?,?,?,?,?,?,?,?,?)", [
        (1, None, "Notes", None, None, 0, None, None, 0, 0),
        (2, None, "Recently Deleted", None, None, 0, None, None, 1, 0),
        (10, "Garage", None, 1000, 800000000, 0, 100, 1, None, 0),
        (11, "Old", None, 1000, 1000, 0, 101, 1, None, 0),
        (12, "Vault", None, 1000, 800000000, 1, 102, 1, None, 0),
        (13, "Gone", None, 1000, 800000000, 0, 103, 2, None, 0),
    ])
    con.executemany("insert into ZICNOTEDATA values (?,?)", [(100, note_blob("Door code is 4417\nFilter 20x25x1\nkey sk-abcdefghijklmnopqrstuvwxyz")), (101, note_blob("old")), (102, note_blob("hidden")), (103, note_blob("trash"))])
    con.commit()
    return path


def reminders_db(folder):
    con = sqlite3.connect(Path(folder) / "Data-A.sqlite")
    con.execute("create table ZREMCDREMINDER (ZCKIDENTIFIER text, ZLIST integer, ZTITLE text, ZNOTES text, ZCOMPLETED integer, ZDUEDATE real, ZCREATIONDATE real, ZLASTMODIFIEDDATE real, ZCOMPLETIONDATE real, ZMARKEDFORDELETION integer)")
    con.execute("create table ZREMCDBASELIST (Z_PK integer, ZNAME text)")
    con.execute("insert into ZREMCDBASELIST values (1, 'Home Todos')")
    con.executemany("insert into ZREMCDREMINDER values (?,?,?,?,?,?,?,?,?,?)", [("R1", 1, "Replace furnace filter", "", 0, 800100000, 799000000, 800000000, None, 0), ("R2", 1, "Deleted", "", 0, None, 1, 800000000, None, 1)])
    con.commit()


class AppleItemsTest(unittest.TestCase):
    def test_reads_changed_notes_skips_trash_and_masks_secrets(self):
        folder = tempfile.mkdtemp()
        rows, until = ingest.apple_items("notes", "2020-01-01", {"notes": {}}, where=notes_db(folder), judge=lambda lines: ["code is" in line for line in lines])
        self.assertEqual(["p10", "p12"], [row["id"] for row in rows])
        self.assertEqual("[secret]\nFilter 20x25x1\nkey [secret]", rows[0]["body"])
        self.assertEqual(("", True), (rows[1]["body"], rows[1]["locked"]))
        self.assertEqual("2026-05-09T06:13:20.000Z", until)

    def test_reads_reminders_with_their_list(self):
        folder = tempfile.mkdtemp()
        reminders_db(folder)
        rows, _ = reminders.collect("2020-01-01", folder)
        self.assertEqual([("R1", "Home Todos", "Replace furnace filter", "2026-05-10T10:00:00.000Z")], [(r["id"], r["list"], r["title"], r["due"]) for r in rows])

    def test_skips_a_source_missing_from_the_config(self):
        self.assertEqual(([], "x"), ingest.apple_items("reminders", "x", {}))

    def test_a_reader_failure_keeps_the_watermark(self):
        self.assertEqual(([], "2025"), ingest.apple_items("notes", "2025", {"notes": {}}, where="/nonexistent/NoteStore.sqlite"))

    def test_mask_leaves_clean_text_alone(self):
        rows = mask.mask_rows([{"title": "Soccer", "body": "Practice at 5"}], ("title", "body"), judge=lambda lines: [False] * len(lines))
        self.assertEqual([{"title": "Soccer", "body": "Practice at 5"}], rows)

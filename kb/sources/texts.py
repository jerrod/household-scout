import csv
import datetime
import sqlite3
from pathlib import Path

from kb.schema import REPO

CHAT = Path.home() / "Library/Messages/chat.db"
APPLE_EPOCH = 978307200
THREAD = """select m.ROWID, m.date, m.is_from_me, coalesce(h.id, ''), m.text from message m
left join handle h on h.ROWID = m.handle_id join chat_message_join j on j.message_id = m.ROWID
where j.chat_id = (select chat_id from chat_message_join where message_id = ?) and m.ROWID >= ? and m.text is not null
order by m.date limit ?"""


def window_start(window, repo=REPO):
    with (repo / "texts/window-map.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["window"] == window:
                return int(row["first_message_rowid"])
    return None


def read_thread(rowid, limit=40, chat=CHAT):
    con = sqlite3.connect(f"file:{chat}?mode=ro", uri=True)
    lines = []
    for message, date, mine, handle, text in con.execute(THREAD, (rowid, rowid, limit)):
        when = datetime.datetime.fromtimestamp(date / 1e9 + APPLE_EPOCH).strftime("%Y-%m-%d %H:%M")
        lines.append({"id": message, "when": when, "from": "me" if mine else handle, "text": text})
    return lines

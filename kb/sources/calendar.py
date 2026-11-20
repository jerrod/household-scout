import datetime
import sqlite3
from pathlib import Path

DATABASE = Path.home() / "Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb"
APPLE_EPOCH = 978307200
FIRST_YEAR = 1970
SKIPPED_CALENDARS = {"Holidays in United States", "US Holidays", "Scheduled Reminders", "Found in Natural Language", "Found in Mail"}
SKIPPED_TITLES = {"busy", "free", ""}
FREQUENCY = {1: "daily", 2: "weekly", 3: "monthly", 4: "yearly"}
QUERY = """
select i.ROWID, c.title, i.summary, i.start_date, i.end_date, i.all_day, i.start_tz, l.title, l.address,
       (select r.frequency || ':' || r.interval || ':' || coalesce(r.end_date, '') from Recurrence r where r.owner_id = i.ROWID limit 1)
from CalendarItem i join Calendar c on c.ROWID = i.calendar_id left join Location l on l.ROWID = i.location_id
where (i.hidden = 0 or i.hidden is null) and i.start_date is not null order by i.start_date, i.ROWID
"""


def moment(seconds, floating):
    stamp = datetime.datetime.fromtimestamp(seconds + APPLE_EPOCH, datetime.timezone.utc)
    return stamp if floating else stamp.astimezone()


def repeat_text(raw):
    if not raw:
        return ""
    frequency, interval, end = raw.split(":")
    text = FREQUENCY.get(int(frequency), "repeats")
    if int(interval or 1) > 1:
        text = f"every {interval} {text}"
    if end:
        text += " until " + moment(float(end), False).strftime("%Y-%m-%d")
    return "repeats " + text


def clean_title(title):
    title = (title or "").strip()
    while title.endswith("(copy)"):
        title = title[: -len("(copy)")].strip()
    return title


def read_events(database=DATABASE):
    con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    events = []
    for rowid, calendar, title, start, end, all_day, zone, place, address, repeat in con.execute(QUERY):
        title = clean_title(title)
        if (calendar or "").strip() in SKIPPED_CALENDARS or title.lower() in SKIPPED_TITLES:
            continue
        begins = moment(start, bool(all_day) or zone == "_float")
        if begins.year < FIRST_YEAR:
            continue
        where = " ".join((place or address or "").split())
        events.append(
            {
                "rowid": rowid,
                "calendar": (calendar or "").strip(),
                "title": " ".join(title.split()),
                "date": begins.strftime("%Y-%m-%d"),
                "time": "" if all_day else begins.strftime("%H:%M"),
                "where": where,
                "repeat": repeat_text(repeat),
            }
        )
    return events

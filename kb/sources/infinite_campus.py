import hashlib
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from kb import household  # noqa: E402

HOST = household.source("infinite_campus").get("host", "")
APP_NAME = household.source("infinite_campus").get("app_name", "")
LOGIN = household.STATE / "infinite-campus.env"
PORTAL = HOST + "nav-wrapper/parent/portal/parent/classroom/curriculum/resource/{work}/view?classroomSectionID={section}&appName=" + APP_NAME


def local(stamp):
    import datetime
    import zoneinfo
    if not stamp:
        return None
    moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    moment = moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
    return moment.astimezone(zoneinfo.ZoneInfo(household.TIMEZONE)).strftime("%Y-%m-%d %H:%M")


def credentials(path=LOGIN):
    found = dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
    return found["SCOUT_INFINITE_CAMPUS_USERNAME"].strip().strip("'\""), found["SCOUT_INFINITE_CAMPUS_PASSWORD"].strip().strip("'\"")


def session(username, password):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    form = urllib.parse.urlencode({"username": username, "password": password, "appName": APP_NAME, "portalLoginPage": "parents"}).encode()
    with opener.open(HOST + "verify.jsp?nonBrowser=true", form) as response:
        answer = re.search(r"<AUTHENTICATION>([^<]+)</AUTHENTICATION>", response.read().decode(errors="replace"), re.I)
    if not answer or answer.group(1).strip().lower() != "success":
        raise RuntimeError("Infinite Campus refused the parent login")
    return opener


def get(opener, path, params=None):
    url = HOST + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with opener.open(urllib.request.Request(url, headers={"Accept": "application/json"})) as response:
        return json.loads(response.read())


def snapshot(opener):
    students = []
    for student in get(opener, "api/portal/students"):
        person = {"personID": student["personID"]}
        name = student["firstName"]
        roster = {str(s["sectionID"]): {"course": s["courseName"], "teacher": s.get("teacherDisplay")} for s in get(opener, "resources/portal/roster", person)}
        categories = {}
        for section in roster:
            for task in (get(opener, f"resources/portal/grades/detail/{section}", person) or {}).get("details") or []:
                for category in task.get("categories") or []:
                    for work in category.get("assignments") or []:
                        categories[work["objectSectionID"]] = category.get("name")
        assignments = [{"id": a["objectSectionID"], "course": a["courseName"], "title": a["assignmentName"].strip(), "due": a.get("dueDate"), "due_local": local(a.get("dueDate")),
                        "assigned": a.get("assignedDate"), "score": a.get("scorePoints"), "points": a.get("totalPoints"), "missing": a.get("missing"),
                        "late": a.get("late"), "turned_in": a.get("turnedIn"), "incomplete": a.get("incomplete"), "comment": (a.get("comments") or "").strip() or None,
                        "category": categories.get(a["objectSectionID"]), "url": PORTAL.format(work=a["objectSectionID"], section=a["sectionID"])}
                       for a in get(opener, "api/portal/assignment/listView", person)]
        grades = [{"course": c.get("courseName") or roster.get(str(c["sectionID"]), {}).get("course"), "term": f"{t['termName']} {t['taskName']}",
                   "percent": t["progressPercent"], "letter": t.get("progressScore"), "updated": t.get("modifiedDate")}
                  for e in get(opener, "resources/portal/grades", person) for c in e.get("courses") or [] for t in c.get("gradingTasks") or []
                  if t.get("hasAssignments") and t.get("progressPercent") is not None]
        attendance = [{"id": ev["attendanceID"], "date": ev["date"], "code": ev.get("code"), "description": ev.get("description"), "excused": ev.get("excuse") == "E",
                       "course": (ev.get("sectionPlacements") or [{}])[0].get("courseName")}
                      for e in student.get("enrollments") or [] for g in get(opener, "resources/portal/attendance/events", {"enrollmentID": e["enrollmentID"], **person}) for ev in g.get("events") or []]
        students.append({"student": name, "courses": roster, "grades": grades, "assignments": assignments, "attendance": attendance})
    return students


def changes(students, known):
    rows, seen = [], {}
    for record in students:
        for kind in ("grades", "assignments", "attendance"):
            for item in record[kind]:
                key = f"{record['student']}:{kind}:{item.get('id') or item['course'] + ':' + item['term']}"
                digest = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]
                seen[key] = digest
                if known.get(key) != digest:
                    rows.append({"kind": kind[:-1] if kind != "attendance" else "attendance", "student": record["student"], **item})
    return rows, seen


def collect(known, folder, login=LOGIN):
    students = snapshot(session(*credentials(login)))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "infinite-campus.json").write_text(json.dumps(students, indent=1, ensure_ascii=False))
    return changes(students, known)

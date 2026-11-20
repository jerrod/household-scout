import json
import urllib.parse
import urllib.request
from pathlib import Path
from kb import household  # noqa: E402

HOST = household.source("canvas").get("host", "")
TOKENS = household.STATE
STUDENTS = household.source("canvas").get("students", {})
FIRST_SYNC = household.source("canvas").get("first_sync", "2026-08-01T00:00:00Z")


def token(name):
    return (TOKENS / name).read_text().strip()


def get(path, secret, params=None, opener=urllib.request.urlopen):
    url = HOST + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    found = []
    while url:
        with opener(urllib.request.Request(url, headers={"Authorization": f"Bearer {secret}"})) as response:
            page = json.loads(response.read())
            found += page if isinstance(page, list) else [page]
            links = response.headers.get("Link", "") or ""
        url = next((part.split(";")[0].strip("<> ") for part in links.split(",") if 'rel="next"' in part), None)
    return found


def local(stamp):
    import datetime
    import zoneinfo
    if not stamp:
        return None
    return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(zoneinfo.ZoneInfo(household.TIMEZONE)).strftime("%Y-%m-%d %H:%M")


def changed(item, since, *keys):
    return any((item.get(key) or "") > since for key in keys)


def collect(since_by_student, opener=urllib.request.urlopen):
    rows, newest = [], {}
    for student, file in STUDENTS.items():
        secret = token(file)
        since = since_by_student.get(student, FIRST_SYNC)
        newest[student] = since
        courses = get("/api/v1/courses", secret, {"enrollment_state": "active", "per_page": 100}, opener)
        for course in courses:
            name = course.get("name", "")
            assignments = get(f"/api/v1/courses/{course['id']}/assignments", secret, {"per_page": 100}, opener)
            mine = {row["assignment_id"]: row for row in get(f"/api/v1/courses/{course['id']}/students/submissions", secret, {"student_ids[]": "self", "per_page": 100}, opener)}
            for item in assignments:
                submission = mine.get(item["id"]) or {}
                if changed(item, since, "updated_at") or changed(submission, since, "graded_at", "submitted_at"):
                    rows.append({"kind": "assignment", "student": student, "course": name, "id": item["id"], "name": item.get("name"), "due_at": item.get("due_at"), "due_local": local(item.get("due_at")),
                                 "points_possible": item.get("points_possible"), "score": submission.get("score"), "grade": submission.get("grade"),
                                 "submitted_at": submission.get("submitted_at"), "graded_at": submission.get("graded_at"), "missing": submission.get("missing"),
                                 "late": submission.get("late"), "url": item.get("html_url"), "updated_at": item.get("updated_at"),
                                 "submission_type": submission.get("submission_type"), "submitted_link": submission.get("url") if submission.get("submission_type") == "online_url" else None,
                                 "submitted_text": submission.get("body"),
                                 "files": [{"name": a.get("display_name"), "url": a.get("url"), "type": a.get("content-type")} for a in submission.get("attachments") or []]})
        codes = [f"course_{course['id']}" for course in courses]
        if codes:
            for item in get("/api/v1/announcements", secret, {"context_codes[]": codes, "start_date": since[:10], "per_page": 100}, opener):
                rows.append({"kind": "announcement", "student": student, "course": item.get("context_code"), "id": item["id"], "title": item.get("title"),
                             "author": (item.get("author") or {}).get("display_name"), "posted_at": item.get("posted_at"), "message": item.get("message"), "url": item.get("html_url")})
        for item in get("/api/v1/conversations", secret, {"per_page": 100}, opener):
            if changed(item, since, "last_message_at"):
                rows.append({"kind": "message", "student": student, "id": item["id"], "subject": item.get("subject"), "last_message": item.get("last_message"),
                             "last_message_at": item.get("last_message_at"), "participants": [p.get("name") for p in item.get("participants") or []]})
        for row in rows:
            for key in ("updated_at", "graded_at", "submitted_at", "posted_at", "last_message_at"):
                if row.get("student") == student and (row.get(key) or "") > newest[student]:
                    newest[student] = row[key]
    return rows, newest


def download_files(rows, folder, opener=urllib.request.urlopen):
    from kb.sources.mail import write_attachment_texts
    for row in rows:
        saved = []
        for index, item in enumerate(row.get("files") or []):
            target = folder / row["student"] / str(row["id"]) / f"{index}-{Path(item['name'] or 'file').name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            with opener(urllib.request.Request(item["url"], headers={"Authorization": f"Bearer {token(STUDENTS[row['student']])}"})) as response:
                target.write_bytes(response.read())
            saved.append(str(target))
        write_attachment_texts(saved)
        if saved:
            row["saved_files"] = saved
    return rows


def course_snapshots(folder, opener=urllib.request.urlopen):
    import hashlib
    import html as markup
    import re
    saved = []
    for student, file in STUDENTS.items():
        secret = token(file)
        for course in get("/api/v1/courses", secret, {"enrollment_state": "active", "per_page": 100, "include[]": "syllabus_body"}, opener):
            modules = get(f"/api/v1/courses/{course['id']}/modules", secret, {"include[]": "items", "per_page": 100}, opener)
            body = course.get("syllabus_body") or ""
            text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</tr>", "\n", body)
            text = re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\xa0]+", " ", markup.unescape(re.sub(r"<[^>]+>", " ", text)))).strip()
            outline = "\n".join(f"- {module['name']}" + "".join(f"\n  - {item.get('title')}" for item in module.get("items") or []) for module in modules)
            snapshot = f"# {course['name']}\n\nStudent: {student}\n\n## Syllabus\n\n{text}\n\n## Modules\n\n{outline}\n"
            slug = re.sub(r"[^a-z0-9]+", "-", course["name"].lower()).strip("-")
            target = folder / "courses" / f"{student.lower()}-{slug}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(snapshot)
            saved.append({"student": student, "course": course["name"], "path": str(target), "sha": hashlib.sha256(snapshot.encode()).hexdigest()})
    return saved

import json
import subprocess

SCRIPT = """
const out = [];
const iso = d => d ? d.toISOString() : "";
Application("Reminders").lists().forEach(l => {
  const r = l.reminders, ids = r.id(), names = r.name(), bodies = r.body(), done = r.completed(),
        due = r.dueDate(), made = r.creationDate(), changed = r.modificationDate(), finished = r.completionDate();
  for (let i = 0; i < ids.length; i++)
    out.push({list: l.name(), id: ids[i].split("/").pop(), title: names[i], body: bodies[i] || "", completed: done[i],
              due: iso(due[i]), created: iso(made[i]), modified: iso(changed[i]) || iso(made[i]), completed_at: iso(finished[i])});
});
JSON.stringify(out);
"""


def read_all(run=subprocess.run):
    done = run(["osascript", "-l", "JavaScript", "-e", SCRIPT], capture_output=True, text=True, timeout=900, check=True)
    return json.loads(done.stdout)


def collect(since, run=subprocess.run):
    rows = [row for row in read_all(run) if row["modified"] > since]
    return rows, max([row["modified"] for row in rows], default=since)

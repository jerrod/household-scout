import json
import subprocess

SCRIPT = """
const out = [];
Application("Notes").accounts().forEach(a => a.folders().forEach(f => f.notes().forEach(n => {
  const locked = n.passwordProtected();
  out.push({account: a.name(), folder: f.name(), id: n.id().split("/").pop(), title: n.name(),
            created: n.creationDate().toISOString(), modified: n.modificationDate().toISOString(),
            locked: locked, body: locked ? "" : n.plaintext()});
})));
JSON.stringify(out);
"""


def read_all(run=subprocess.run):
    done = run(["osascript", "-l", "JavaScript", "-e", SCRIPT], capture_output=True, text=True, timeout=900, check=True)
    return json.loads(done.stdout)


def collect(since, run=subprocess.run):
    rows = [row for row in read_all(run) if row["modified"] > since]
    return rows, max([row["modified"] for row in rows], default=since)

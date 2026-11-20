import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kb import jev  # noqa: E402
from kb.facts import read_facts, write_facts  # noqa: E402

TEXT = {".txt", ".md", ".csv", ".json", ".jsonl", ".eml", ".html", ".htm", ".ics", ".js", ".py", ".yaml", ".yml", ".env", ".log"}
SHAPES = re.compile(r"sk-[A-Za-z0-9_-]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|shippo_(live|test)_[a-f0-9]{20,}"
                    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----")
QUESTION = {"secret": {"type": "noul", "instructions": "The `text` contains a password, passcode, PIN, API key, access token, recovery code, seed phrase, or a full bank account, card or social security number."}}
WINDOW, STEP, THRESHOLD = 1500, 1200, 0.8
SCANNED = ("documents/archive/", "documents/library/")
INDEXES = ("documents/sources.csv", "documents/summaries.csv", "documents/fact-links.csv")


def text_of(path):
    sidecar = path.with_name(path.name + ".txt")
    source = path if path.suffix.lower() in TEXT else sidecar if sidecar.exists() else None
    return source.read_text(errors="replace") if source else None


def windows(text):
    return [text[start:start + WINDOW] for start in range(0, max(len(text) - WINDOW, 0) + 1, STEP)] or [text]


def flagged(paths, root=REPO):
    hits, unread = [], []
    for name in paths:
        path = root / name
        if not name.startswith(SCANNED) or name.endswith(".txt") and (root / name[:-4]).exists() or not path.is_file():
            continue
        text = text_of(path)
        if text is None:
            unread.append(name)
            continue
        if SHAPES.search(text) or any(a["secret"]["noul"] >= THRESHOLD for a in jev.ask_many([{"text": w} for w in windows(text)], QUESTION)):
            hits.append(name)
    return hits, unread


def destination(name):
    return "vault/" + name.removeprefix("documents/")


def move(names, root=REPO):
    renames = {}
    for name in names:
        target = destination(name)
        for suffix in ("", ".txt"):
            old, new = root / (name + suffix), root / (target + suffix)
            if old.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
        renames[name] = target
    if not renames:
        return renames
    for index in INDEXES:
        path = root / index
        if path.exists():
            text = path.read_text()
            for old, new in renames.items():
                text = text.replace(old, new)
            path.write_text(text)
    facts = read_facts(root / "facts")
    for fact in facts:
        for old, new in renames.items():
            fact["source"] = fact["source"].replace(f"file:{old}", f"file:{new}")
    write_facts(facts, root / "facts")
    return renames


def staged(root=REPO):
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=A"], cwd=root, capture_output=True, text=True, check=True)
    return out.stdout.split()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Move new files that hold a secret into vault/ before they are committed")
    parser.add_argument("paths", nargs="*", help="files to scan; default: files staged for addition")
    args = parser.parse_args()
    hits, unread = flagged(args.paths or staged())
    for old, new in move(hits).items():
        print(f"moved {old} -> {new}")
    if unread:
        print(f"{len(unread)} files have no text to scan, such as images without a text sidecar")

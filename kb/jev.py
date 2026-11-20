import hashlib
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URL = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = Path.home() / ".config/typesafe/api-key"
CACHE = Path(__file__).resolve().parent.parent / ".kb" / "jev-cache.jsonl"


def ask(state, questions, key=None):
    body = json.dumps({"state": state, "model": "jev-latest", "questions": questions}).encode()
    headers = {"Authorization": "Bearer " + (key or KEY_FILE.read_text().strip()), "Content-Type": "application/json"}
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=headers), timeout=60) as response:
                return json.load(response)["answers"]
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def digest(state, questions):
    return hashlib.sha256(json.dumps([state, questions], sort_keys=True).encode()).hexdigest()


class Cache:
    def __init__(self, path=None):
        self.path = path = path or CACHE
        self.known = {}
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.known[row["key"]] = row["answers"]

    def save(self, key, answers):
        self.known[key] = answers
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as handle:
            handle.write(json.dumps({"key": key, "answers": answers}) + "\n")


def ask_many(states, questions, cache=None, workers=8):
    cache = cache or Cache()
    keys = [digest(state, questions) for state in states]
    missing = [(key, state) for key, state in zip(keys, states) if key not in cache.known]
    key = KEY_FILE.read_text().strip() if missing else None
    with ThreadPoolExecutor(workers) as pool:
        for (code, _), answers in zip(missing, pool.map(lambda pair: ask(pair[1], questions, key), missing)):
            cache.save(code, answers)
    return [cache.known[code] for code in keys]

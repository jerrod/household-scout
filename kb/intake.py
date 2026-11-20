import json
import os
import urllib.request
from pathlib import Path

from kb.schema import REPO
from kb import household  # noqa: E402

SERVER = os.environ.get("KB_SERVER", household.source("intake").get("server", ""))
TOKEN_FILE = household.STATE / "extractor-token"


def request(path, method="GET", data=None, opener=urllib.request.urlopen):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Authorization": f"Bearer {TOKEN_FILE.read_text().strip()}", "Content-Type": "application/json"}
    with opener(urllib.request.Request(SERVER + path, data=body, method=method, headers=headers)) as response:
        return response.read()


def pull(day, opener=urllib.request.urlopen):
    folder = REPO / "inbox" / day / "intake"
    folder.mkdir(parents=True, exist_ok=True)
    items = json.loads(request("/api/v1/intake/pending", opener=opener))
    for item in items:
        if item["kind"] == "document":
            (folder / f"{item['id']}-{item['filename']}").write_bytes(request(f"/api/v1/intake/{item['id']}/content", opener=opener))
    (folder / "items.json").write_text(json.dumps(items, indent=1))
    return folder, items


def resolve(item_id, status, outcome, opener=urllib.request.urlopen):
    return json.loads(request(f"/api/v1/intake/{item_id}/resolve", "POST", {"status": status, "outcome": outcome}, opener=opener))

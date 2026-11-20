import argparse
import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kb.sources import slack  # noqa: E402
from kb.sources.mail import write_attachment_texts  # noqa: E402
from kb import household  # noqa: E402

GAP = 3 * 3600
CHUNK_MESSAGES = 300
CHUNK_CHARS = 90000
MAX_FILE = 2 * 1024 ** 3
GIT_LIMIT = 50 * 1024 * 1024
LARGE = household.STATE / "slack-large"
LINK = re.compile(r"<(https?://[^>|]+)(?:\|[^>]*)?>|(?<![<|])(https?://[^\s>|)\]]+)")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60] or "file"


def history(secret, conversation):
    messages = []
    for message in slack.pages(secret, "conversations.history", "messages", channel=conversation):
        messages.append(message)
        if message.get("reply_count"):
            replies = slack.pages(secret, "conversations.replies", "messages", channel=conversation, ts=message["ts"])
            messages.extend(r for r in replies if r["ts"] != message["ts"])
    return sorted(messages, key=lambda m: float(m["ts"]))


def urls(message):
    found = [a or b for a, b in LINK.findall(message.get("text", ""))]
    for attachment in message.get("attachments", []):
        found += [attachment[key] for key in ("from_url", "original_url", "title_link") if attachment.get(key)]
    return list(dict.fromkeys(u.rstrip(".,") for u in found))


def download(secret, item, when, place, root):
    url = item.get("url_private_download") or item.get("url_private")
    if not url or item.get("mode") in ("tombstone", "hidden_by_limit") or item.get("size", 0) > MAX_FILE:
        return None
    name = item.get("name") or item.get("title") or item["id"]
    stem, _, suffix = name.rpartition(".")
    filename = f"{when[:10]}_{slug(place)}_{item['id']}_{slug(stem or name)}" + (f".{suffix.lower()}" if stem else "")
    target = (LARGE if item.get("size", 0) > GIT_LIMIT else root) / when[:4] / filename
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {secret}"})
        with urllib.request.urlopen(request, timeout=120) as response:
            target.write_bytes(response.read())
        write_attachment_texts([target])
    return target


def sessions(messages, gap=GAP):
    roots, threads = [], {}
    for message in messages:
        parent = message.get("thread_ts")
        if parent and parent != message["ts"]:
            threads.setdefault(parent, []).append(message)
        else:
            roots.append(message)
    groups, last = [], None
    for message in roots:
        if last is None or float(message["ts"]) - last > gap:
            groups.append([])
        groups[-1].append(message)
        groups[-1].extend(threads.pop(message["ts"], []))
        last = float(message["ts"])
    groups.extend(sorted(threads.values(), key=lambda t: float(t[0]["ts"])))
    return groups


def chunks(groups, size=CHUNK_MESSAGES, chars=CHUNK_CHARS):
    batch, count, length = [], 0, 0
    for group in groups:
        text = sum(len(m.get("text", "")) for m in group)
        if batch and (count + len(group) > size or length + text > chars):
            yield batch
            batch, count, length = [], 0, 0
        batch.append(group)
        count, length = count + len(group), length + text
    if batch:
        yield batch


def transcript(place, batch, people, files):
    lines = [f"# Slack: {place}", ""]
    for group in batch:
        lines.append(f"## Conversation starting {slack.local(group[0]['ts'])}")
        for message in group:
            who = people.get(message.get("user", ""), message.get("username") or "unknown")
            reply = "  ↳ " if message.get("thread_ts") and message["thread_ts"] != message["ts"] else ""
            shared = " ".join(a.get("fallback") or a.get("text") or "" for a in message.get("attachments", []))
            body = " ".join(part for part in (message.get("text", ""), f"[shared: {shared}]" if shared else "") if part)
            if message.get("subtype") == "bot_message" and message.get("attachments"):
                who = message["attachments"][0].get("author_name") or who
            lines.append(f"{reply}[{slack.local(message['ts'])}] {who} (ts {message['ts']}): {body}")
            for item in message.get("files", []):
                saved = files.get(item.get("id"))
                lines.append(f"{reply}  file: {item.get('name') or item.get('title')} -> {saved or 'not downloaded'}")
        lines.append("")
    return "\n".join(lines)


def export(out, secret=None):
    secret = secret or slack.token()
    people = {u["id"]: u.get("real_name") or u.get("name") for u in slack.pages(secret, "users.list", "members")}
    archive = REPO / "documents/archive/slack"
    out.mkdir(parents=True, exist_ok=True)
    links, number = [], 0
    for conversation in slack.pages(secret, "users.conversations", "channels", types=slack.TYPES, exclude_archived="false"):
        place = slack.name_of(conversation, people)
        messages = history(secret, conversation["id"])
        files = {}
        for message in messages:
            when = slack.local(message["ts"])
            for item in message.get("files", []):
                saved = download(secret, item, when, place, archive)
                files[item.get("id")] = (saved.relative_to(REPO).as_posix() if saved.is_relative_to(REPO) else str(saved)) if saved else None
            for url in urls(message):
                links.append({"date": when[:10], "time": when[11:], "channel": place,
                              "from": people.get(message.get("user", ""), message.get("username") or "unknown"), "url": url, "ts": message["ts"]})
        for batch in chunks(sessions(messages)):
            number += 1
            start = slack.local(batch[0][0]["ts"])[:10]
            (out / f"{number:04d}_{start}_{slug(place)}.md").write_text(transcript(place, batch, people, files))
    with open(REPO / "documents/slack-links.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "time", "channel", "from", "url", "ts"])
        writer.writeheader()
        writer.writerows(sorted(links, key=lambda r: float(r["ts"])))
    return number, len(links)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export every Slack conversation as thread-aware transcript chunks, files and a link catalog")
    parser.add_argument("--out", default=str(REPO / "inbox/slack-backfill"))
    args = parser.parse_args()
    print("%d chunks, %d links" % export(Path(args.out)))

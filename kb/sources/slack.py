import datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo
from pathlib import Path
from kb import household  # noqa: E402

API = "https://slack.com/api/"
LOGIN = household.STATE / "slack.env"
TYPES = "public_channel,private_channel,mpim,im"
THREAD_DAYS = 30


def token(path=LOGIN):
    found = dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
    return found["SLACK_USER_TOKEN"].strip().strip("'\"")


def call(secret, method, **params):
    request = urllib.request.Request(API + method + "?" + urllib.parse.urlencode(params), headers={"Authorization": f"Bearer {secret}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                answer = json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 3:
                raise
            time.sleep(int(error.headers.get("Retry-After", "5")))
            continue
        if not answer.get("ok"):
            raise RuntimeError(f"Slack {method}: {answer.get('error')}")
        return answer
    raise RuntimeError(f"Slack {method}: rate limited")


def pages(secret, method, key, **params):
    cursor = ""
    while True:
        answer = call(secret, method, limit=200, cursor=cursor, **params)
        yield from answer.get(key, [])
        cursor = answer.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            return


def local(ts):
    moment = datetime.datetime.fromtimestamp(float(ts), tz=zoneinfo.ZoneInfo(household.TIMEZONE))
    return moment.strftime("%Y-%m-%d %H:%M")


def row(message, place, people, team):
    who = people.get(message.get("user", ""), message.get("username") or message.get("bot_id") or "unknown")
    return {"kind": "slack", "channel": place, "ts": message["ts"], "time": local(message["ts"]), "from": who,
            "text": message.get("text", ""), "thread": message.get("thread_ts") if message.get("thread_ts") != message["ts"] else None,
            "files": [{"name": f.get("name"), "url": f.get("url_private")} for f in message.get("files", [])],
            "link": f"https://{team}.slack.com/archives/{message.get('channel', '')}/p{message['ts'].replace('.', '')}"}


def name_of(conversation, people):
    if conversation.get("is_im"):
        return "DM " + people.get(conversation.get("user", ""), "unknown")
    return conversation.get("name") or conversation["id"]


def collect(known, secret=None):
    secret = secret or token()
    team = call(secret, "auth.test")["url"].split("//")[1].split(".")[0]
    people = {u["id"]: u.get("real_name") or u.get("name") for u in pages(secret, "users.list", "members")}
    rows, seen = [], dict(known)
    for conversation in pages(secret, "users.conversations", "channels", types=TYPES, exclude_archived="true"):
        place, since = name_of(conversation, people), known.get(conversation["id"], "0")
        newest = since
        window = str(max(0.0, float(since) - THREAD_DAYS * 86400)) if float(since) else "0"
        for message in pages(secret, "conversations.history", "messages", channel=conversation["id"], oldest=window):
            found = [message] if float(message["ts"]) > float(since) else []
            if float(message.get("latest_reply", "0")) > float(since):
                replies = pages(secret, "conversations.replies", "messages", channel=conversation["id"], ts=message["ts"], oldest=since)
                found += [r for r in replies if r["ts"] != message["ts"] and float(r["ts"]) > float(since)]
            for item in found:
                if item.get("subtype") in ("channel_join", "channel_leave"):
                    continue
                rows.append(row({**item, "channel": conversation["id"]}, place, people, team))
                newest = max(newest, item["ts"], key=float)
        seen[conversation["id"]] = newest
    rows.sort(key=lambda r: float(r["ts"]))
    return rows, seen

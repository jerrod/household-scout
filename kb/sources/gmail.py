import base64
import email
import json
import urllib.parse
import urllib.request
from email import policy

from kb import household
from kb.sources.mail import body_text, write_attachment_texts

API = "https://gmail.googleapis.com/gmail/v1/users/me/"
TOKEN_URL = "https://oauth2.googleapis.com/token"
LOGIN = household.STATE / "gmail.json"


def access_token(opener=urllib.request.urlopen, login=LOGIN):
    saved = json.loads(login.read_text())
    form = urllib.parse.urlencode({"client_id": saved["client_id"], "client_secret": saved["client_secret"], "refresh_token": saved["refresh_token"], "grant_type": "refresh_token"}).encode()
    with opener(urllib.request.Request(TOKEN_URL, form)) as response:
        return json.loads(response.read())["access_token"]


def call(path, token, params=None, opener=urllib.request.urlopen):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with opener(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})) as response:
        return json.loads(response.read())


def added_ids(start, token, opener):
    ids, page = [], None
    while True:
        params = {"startHistoryId": start, "historyTypes": "messageAdded", **({"pageToken": page} if page else {})}
        reply = call("history", token, params, opener)
        ids += [m["message"]["id"] for h in reply.get("history", []) for m in h.get("messagesAdded", [])]
        page = reply.get("nextPageToken")
        if not page:
            return list(dict.fromkeys(ids)), reply.get("historyId", start)


def save(message_id, token, folder, opener):
    raw = base64.urlsafe_b64decode(call(f"messages/{message_id}", token, {"format": "raw"}, opener)["raw"])
    target = folder / f"gmail-{message_id}"
    target.mkdir(parents=True, exist_ok=True)
    eml = target / f"{message_id}.eml"
    eml.write_bytes(raw)
    message = email.message_from_bytes(raw, policy=policy.default)
    (target / "body.txt").write_text(body_text(message))
    files = []
    for part in message.iter_attachments():
        name = part.get_filename()
        if name:
            path = target / name.replace("/", "_")
            path.write_bytes(part.get_payload(decode=True) or b"")
            files.append(str(path))
    write_attachment_texts(files)
    return {"id": f"gmail-{message_id}", "sender": str(message.get("from", "")), "subject": str(message.get("subject", "")),
            "snippet": (target / "body.txt").read_text()[:300], "saved": str(eml), "files": files}


def collect(known, folder, opener=urllib.request.urlopen, login=LOGIN):
    token = access_token(opener, login)
    if not known.get("history_id"):
        return [], {"history_id": call("profile", token, opener=opener)["historyId"]}
    ids, latest = added_ids(known["history_id"], token, opener)
    return [save(i, token, folder, opener) for i in ids], {"history_id": latest}

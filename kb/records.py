import re

from kb.schema import ENTITY_FOLDERS, REPO

DOCUMENT = re.compile(r"`((?:documents|vault)/(?:archive|library)/[^`]+)`")
LINK = re.compile(r"(?<![\w/-])((?:%s)/[a-z0-9][a-z0-9-]*+)(?!/)" % "|".join(ENTITY_FOLDERS))


def parse_value(raw):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [item.strip().strip("\"'") for item in raw[1:-1].split(",") if item.strip()]
    return raw.strip("\"'")


def parse_record(text):
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return {}, text
    head, body = text[4:].split("\n---", 1)
    fields, key = {}, None
    for line in head.split("\n"):
        if line.startswith("  - ") or line.startswith("- "):
            fields.setdefault(key, [])
            if isinstance(fields[key], list):
                fields[key].append(line.split("- ", 1)[1].strip())
        elif ":" in line:
            key, raw = line.split(":", 1)
            key = key.strip()
            fields[key] = parse_value(raw) if raw.strip() else []
    return fields, body.lstrip("\n")


def links_in(path, fields, body):
    found = {}
    for target in LINK.findall(body):
        found[target] = "mentions"
    for folder, key in ENTITY_FOLDERS.items():
        values = fields.get(key, [])
        for value in values if isinstance(values, list) else [values]:
            if value and value != "unknown":
                found[value if "/" in value else f"{folder}/{value}"] = key
    found.pop(path, None)
    return sorted((relation, target) for target, relation in found.items())


def documents_in(body):
    return sorted({path for path in DOCUMENT.findall(body) if not path.endswith(("/", "INDEX.md"))})


def read_records(repo=REPO):
    records = []
    for folder, kind in ENTITY_FOLDERS.items():
        for file in sorted((repo / folder).glob("*.md")):
            if file.name == "INDEX.md":
                continue
            fields, body = parse_record(file.read_text())
            path = f"{folder}/{file.stem}"
            records.append({"path": path, "folder": folder, "kind": kind, "fields": fields, "body": body, "links": links_in(path, fields, body), "documents": documents_in(body)})
    return records

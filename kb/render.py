def fact_line(fact):
    when = f"{fact['date']} {fact['time']}".strip()
    who = fact["person"] or "-"
    money = f" ${fact['amount']:,.2f}" if isinstance(fact["amount"], float) else ""
    entity = f" [{fact['entity']}]" if fact["entity"] else ""
    value = f" {{{fact['value']}}}" if fact["value"] and not money else ""
    return f"{fact['id']} {when} {who} {fact['domain']}/{fact['kind']}{entity} {fact['summary']}{value}{money} ({fact['source'] or 'no source'})"


def row_line(row):
    return " | ".join("" if value is None else str(value) for value in row.values())


def record_text(record):
    lines = [f"# {record['name']}  ({record['path']}.md)"]
    for key, value in record["fields"].items():
        if key != "name" and value not in ("", [], "unknown"):
            lines.append(f"{key}: {', '.join(value) if isinstance(value, list) else value}")
    lines += ["", record["body"].strip()]
    for label in ("links_to", "linked_from"):
        if record[label]:
            lines += ["", f"## {label.replace('_', ' ')}", *record[label]]
    if record.get("documents"):
        lines += ["", "## documents", *record["documents"]]
    if record["facts"]:
        lines += ["", "## facts", *(fact_line(fact) for fact in record["facts"])]
    if record["ledger"]:
        lines += ["", "## ledger", *(f"{row['date']} ${row['amount']:,.2f} {row['summary']} ({row['source']})" for row in record["ledger"])]
    return "\n".join(lines)


def source_text(found):
    lines = []
    for item in found:
        if "thread" in item:
            lines.append(f"== {item['source']}")
            lines += [f"{line['when']} {line['from']}: {line['text']}" for line in item["thread"]]
        elif "mail" in item:
            mail = item["mail"]
            lines.append(f"== {item['source']} {mail.get('sender', '')} | {mail.get('subject', '')}")
            lines.append(mail.get("body") or "(no local copy of the mail body)")
            if mail.get("attachments"):
                lines.append("attachments: " + ", ".join(mail["attachments"]))
        else:
            lines.append(f"== {item['source']}: {item['note']}")
    return "\n".join(lines)


def org_text(found):
    lines = [f"# {found['name']}  (organization, {found['kind']})"]
    if found["record"]:
        lines.append(f"record: {found['record']}")
    lines.append("people: " + ", ".join(f"{person or 'no person'} {count}" for person, count in found["people"].items()))
    lines += ["", "## names in the sources", *(f"{row['facts']:5d}  {row['name']}" + (f"  [{row['unit']}]" if row["unit"] else "") for row in found["names"])]
    if found["documents"]:
        lines += ["", "## documents", *found["documents"]]
    lines += ["", f"## facts ({len(found['facts'])} of {found['fact_count']})", *(fact_line(fact) for fact in found["facts"])]
    return "\n".join(lines)


def neighbors_text(found):
    lines = [f"# {found['node']}"]
    for label, rows in (("out", found["out"]), ("in", found["in"])):
        lines += [f"{'->' if label == 'out' else '<-'} {row['relation']}: {row['node']}" + (f" ({row['n']})" if row["n"] > 1 else "") for row in rows]
    return "\n".join(lines)

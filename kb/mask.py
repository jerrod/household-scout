from kb.secret_scan import QUESTION, SHAPES, THRESHOLD

MASK = "[secret]"


def jev_judge(lines):
    from kb import jev
    return [a["secret"]["noul"] >= THRESHOLD for a in jev.ask_many([{"text": line} for line in lines], QUESTION)]


def mask_rows(rows, fields, judge=jev_judge):
    lines = sorted({line for row in rows for field in fields for line in SHAPES.sub(MASK, row[field]).splitlines() if line.strip()})
    secret = {line for line, hit in zip(lines, judge(lines) if lines else []) if hit}
    for row in rows:
        for field in fields:
            row[field] = "\n".join(MASK if line in secret else line for line in SHAPES.sub(MASK, row[field]).splitlines())
    return rows

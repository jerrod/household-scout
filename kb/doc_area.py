from kb import jev

AREAS = {
    "household": "A personal or family file: home, property, kids' school or activities, medical, receipts, taxes, insurance, vehicles, pets, travel, family photos or ID.",
    "work": "A work file for an employer or client: meeting notes, deals, product documents, job offers or employment papers.",
    "music_hobby": "Music production, audio plugins, synth presets, games, game development or creative hobby assets.",
    "software": "Source code, a library, a dependency, build output, a design template or developer tooling.",
    "credential": "A password, key, secret, certificate, token or backup code file.",
    "media_generic": "A stock image, icon, font, screenshot, meme or other generic media with no personal content.",
    "other": "Anything else.",
}
QUESTIONS = {"area": {"type": "choice", "instructions": "Which area does the `file` belong to?", "criteria": AREAS}}


def state_of(row):
    return {"file": f"Path: {row['path']}\nType: {row.get('ext', '')}\nText: {(row.get('text') or row.get('text_excerpt') or '')[:500]}"}


def triage(rows, ask=None):
    ask = ask or (lambda states: jev.ask_many(states, QUESTIONS))
    answers = ask([state_of(r) for r in rows]) if rows else []
    return [{"id": r["id"], "area": a["area"]["choice"], "confidence": a["area"]["confidence"]} for r, a in zip(rows, answers)]

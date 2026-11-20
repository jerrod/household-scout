import tempfile
from pathlib import Path

from kb import store
from kb.facts import new_fact, write_facts

VENDOR = """---
type: vendor
name: Acme Roofing
updated: 2026-01-02
trade: roofing
phone: unknown
tags: [roof, shingle]
---

## Notes

- Acme replaced the roof. See property/roof and `work/2023-04-04-roof.md`.
- Warranty: `documents/archive/roof/2023/2023-04-10_acme_warranty.pdf`
"""
PROPERTY = """---
type: property
name: Roof
updated: 2026-01-02
vendor: [acme-roofing]
---

## Notes

- Shingle roof.
"""
FACTS = [
    {"id": "F000001", "date": "2023-04-04", "person": "household", "domain": "home", "kind": "invoice", "entity": "Acme Roofing", "summary": "Roof replacement invoice", "amount": "20598.83", "link": "vendors/acme-roofing", "source": "mail:10"},
    {"id": "F000002", "date": "2024-01-08", "time": "14:00", "person": "Riley", "domain": "health", "kind": "dental", "entity": "Main Street Orthodontics", "summary": "First orthodontist appointment", "source": "calendar:Family"},
    {"id": "F000003", "date": "2024-03-02", "person": "Jordan", "domain": "school", "kind": "grade", "summary": "Math quiz scored 95%", "value": "95%", "source": "window:w7"},
]


def make_repo():
    root = Path(tempfile.mkdtemp())
    for folder in ("facts", "vendors", "property", "people", "organizations", "documents", "expenses", "unread", "documents/archive/roof/2023", "vault/archive/taxes"):
        (root / folder).mkdir(parents=True)
    (root / "vendors/acme-roofing.md").write_text(VENDOR)
    (root / "property/roof.md").write_text(PROPERTY)
    (root / "expenses/ledger.csv").write_text("id,date,vendor,category,kind,amount,summary,mail_id\nP0001,2023-04-28,Acme Roofing,roof,receipt,13796.08,Final roof payment,10\n")
    (root / "unread/invites-and-tickets.csv").write_text("date,kind,sender,subject,source\n2025-01-01,ticket,<a@b.c>,Concert tickets,mail:12\n")
    (root / "documents/archive/roof/2023/2023-04-10_acme_warranty.pdf").write_text("x")
    (root / "vault/archive/taxes/2023_w2.pdf").write_text("x")
    (root / "people/riley.md").write_text("---\ntype: person\nname: Riley Lane\nupdated: 2026-01-02\nfact_name: Riley\n---\n")
    (root / "organizations/organizations.csv").write_text("id,name,kind,record\nmain-street-orthodontics,Main Street Orthodontics,dental,\nacme-roofing,Acme Roofing,contractor,vendors/acme-roofing\n")
    (root / "organizations/names.csv").write_text("name,org,unit\nMain Street Orthodontics,main-street-orthodontics,\n")
    (root / "documents/sources.csv").write_text("path,source\ndocuments/archive/roof/2023/2023-04-10_acme_warranty.pdf,mail:10\n")
    (root / "documents/summaries.csv").write_text("path,title,summary,household\ndocuments/archive/roof/2023/2023-04-10_acme_warranty.pdf,Atlas shingle warranty registration,Lifetime limited warranty for the 2023 roof,true\n")
    (root / "documents/fact-links.csv").write_text("fact,path\nF000003,documents/archive/roof/2023/2023-04-10_acme_warranty.pdf\n")
    (root / "open-items.md").write_text("# Open items\n\nRegister the furnace.\n")
    write_facts([new_fact(**fact) for fact in FACTS], root / "facts")
    return root


def make_index(root):
    return store.connect(root, root / ".kb/kb.sqlite")

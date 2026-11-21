import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb import check, edit, query, records
from kb.facts import new_fact, next_id, read_facts
from tests.fixtures import make_index, make_repo



def fake_jev(answer):
    """Patch Jev's HTTP endpoint; answer(state, questions) returns the answers dict."""
    import contextlib, io, json, tempfile
    from pathlib import Path
    from unittest import mock
    from kb import jev
    folder = Path(tempfile.mkdtemp())
    (folder / "key").write_text("test")
    calls = []

    def urlopen(request, timeout):
        body = json.loads(request.data)
        calls.append(body)
        return contextlib.closing(io.BytesIO(json.dumps({"answers": answer(body["state"], body["questions"])}).encode()))

    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch("urllib.request.urlopen", urlopen))
    stack.enter_context(mock.patch.object(jev, "CACHE", folder / "cache.jsonl"))
    stack.enter_context(mock.patch.object(jev, "KEY_FILE", folder / "key"))
    stack.calls = calls
    return stack


class Records(unittest.TestCase):
    def test_reads_fields_lists_and_links(self):
        found = {record["path"]: record for record in records.read_records(make_repo())}
        vendor = found["vendors/acme-roofing"]
        self.assertEqual(vendor["fields"]["tags"], ["roof", "shingle"])
        self.assertEqual(vendor["links"], [("mentions", "property/roof"), ("mentions", "work/2023-04-04-roof")])
        self.assertEqual(vendor["documents"], ["documents/archive/roof/2023/2023-04-10_acme_warranty.pdf"])
        self.assertEqual(found["property/roof"]["links"], [("vendor", "vendors/acme-roofing")])

    def test_ignores_folder_names_inside_document_paths(self):
        links = records.links_in("x", {}, "`documents/library/property/yard-design/plan.pdf` and vendors/ace-construction.md")
        self.assertEqual(links, [("mentions", "vendors/ace-construction")])

    def test_text_without_frontmatter_has_no_fields(self):
        self.assertEqual(records.parse_record("# Title\n"), ({}, "# Title\n"))


class Queries(unittest.TestCase):
    def setUp(self):
        self.con = make_index(make_repo())
        self.addCleanup(self.con.close)

    def test_filters_facts_by_person_domain_and_date(self):
        rows = query.facts(self.con, person="Riley", domain="health", since="2024-01-01")
        self.assertEqual([row["id"] for row in rows], ["F000002"])
        self.assertEqual(query.count_facts(self.con, domain="school"), 1)
        self.assertEqual(query.facts(self.con, person="Alex"), [])

    def test_text_search_matches_summary_and_value(self):
        self.assertEqual([row["id"] for row in query.facts(self.con, "orthodontist")], ["F000002"])
        self.assertEqual([row["id"] for row in query.facts(self.con, "95%")], ["F000003"])

    def test_search_covers_every_table_and_hides_the_vault(self):
        found = query.search(self.con, "roof")
        self.assertEqual(found["facts"][0]["id"], "F000001")
        self.assertEqual({row["ref"] for row in found["records"]}, {"vendors/acme-roofing", "property/roof"})
        self.assertEqual(found["ledger"][0]["amount"], 13796.08)
        self.assertEqual(query.search(self.con, "w2")["documents"], [])
        self.assertEqual(len(query.search(self.con, "w2", private=True)["documents"]), 1)
        self.assertEqual(query.search(self.con, "Concert")["unread_mail"][0]["source"], "mail:12")

    def test_show_joins_facts_links_and_ledger(self):
        record = query.show(self.con, "acme")
        self.assertEqual(record["path"], "vendors/acme-roofing")
        self.assertEqual(record["facts"][0]["amount"], 20598.83)
        self.assertEqual(record["linked_from"], ["vendor: property/roof"])
        self.assertEqual(record["ledger"][0]["source"], "mail:10")

    def test_show_refuses_an_ambiguous_or_unknown_name(self):
        with self.assertRaises(LookupError):
            query.show(self.con, "roo")
        self.assertEqual(query.show(self.con, "roof")["path"], "property/roof")
        with self.assertRaises(LookupError):
            query.show(self.con, "nothing-like-this")

    def test_listing_and_single_fact(self):
        self.assertEqual(query.listing(self.con, "vendors", ["name", "tags"]), [{"path": "vendors/acme-roofing", "name": "Acme Roofing", "tags": "roof, shingle"}])
        self.assertEqual(query.fact(self.con, "f000003")["person"], "Jordan")
        with self.assertRaises(LookupError):
            query.fact(self.con, "F999999")

    def test_stats_and_sql(self):
        self.assertEqual(query.stats(self.con)["tables"]["facts"], 3)
        self.assertEqual(query.run_sql(self.con, "select count(*) n from facts where amount > 100"), [{"n": 1}])


class Graph(unittest.TestCase):
    def setUp(self):
        self.con = make_index(make_repo())
        self.addCleanup(self.con.close)

    def edges(self, source):
        return {(row["relation"], row["target"]) for row in self.con.execute("select relation, target from edges where source = ?", (source,))}

    def test_fact_links_to_person_organization_record_document_and_payment(self):
        self.assertEqual(self.edges("F000002"), {("about", "people/riley"), ("with", "org:main-street-orthodontics")})
        self.assertEqual(self.edges("F000001"), {("with", "org:acme-roofing"), ("concerns", "vendors/acme-roofing"), ("evidence", "documents/archive/roof/2023/2023-04-10_acme_warranty.pdf"), ("payment", "P0001")})

    def test_reader_titles_make_a_document_searchable_and_link_it_to_its_facts(self):
        self.assertEqual(query.search(self.con, "shingle warranty")["documents"][0]["title"], "Atlas shingle warranty registration")
        self.assertIn(("evidence", "documents/archive/roof/2023/2023-04-10_acme_warranty.pdf"), self.edges("F000003"))
        self.assertEqual(check.run(self.con)["fact link names a missing document or fact"], [])

    def test_a_fact_may_name_a_file_with_spaces_as_its_source(self):
        fact = new_fact(date="2025-01-01", person="household", domain="home", kind="estimate", summary="s", source="file:documents/library/hoa/Oak Hollow Bylaws.pdf")
        self.assertEqual(edit.problems(fact, make_repo()), [])

    def test_record_and_payment_edges_carry_a_relation(self):
        self.assertIn(("vendor", "vendors/acme-roofing"), self.edges("property/roof"))
        self.assertIn(("document", "documents/archive/roof/2023/2023-04-10_acme_warranty.pdf"), self.edges("vendors/acme-roofing"))
        self.assertEqual(self.edges("P0001"), {("paid_to", "vendors/acme-roofing"), ("evidence", "documents/archive/roof/2023/2023-04-10_acme_warranty.pdf")})
        self.assertEqual(self.edges("org:acme-roofing"), {("same_as", "vendors/acme-roofing")})

    def test_organization_page_and_neighbors(self):
        found = query.org(self.con, "orthodontics")
        self.assertEqual((found["id"], found["fact_count"], found["people"]), ("main-street-orthodontics", 1, {"Riley": 1}))
        self.assertEqual(query.org(self.con, "acme-roofing")["documents"], ["documents/archive/roof/2023/2023-04-10_acme_warranty.pdf"])
        with self.assertRaises(LookupError):
            query.org(self.con, "nobody")
        near = query.neighbors(self.con, "vendors/acme-roofing")
        self.assertIn({"relation": "concerns", "node": "facts", "n": 1}, near["in"])
        self.assertIn({"relation": "paid_to", "node": "payments", "n": 1}, near["in"])

    def test_person_record_shows_the_facts_about_that_person(self):
        self.assertEqual([fact["id"] for fact in query.show(self.con, "riley")["facts"]], ["F000002"])


class Checks(unittest.TestCase):
    def test_clean_repo_has_no_errors_and_reports_the_broken_link(self):
        found = check.run(make_index(make_repo()))
        self.assertEqual(found["record links to a missing record"], ["vendors/acme-roofing work/2023-04-04-roof"])
        self.assertEqual([name for name in check.ERRORS if found[name]], ["record links to a missing record"])

    def test_reports_bad_people_dates_types_and_missing_sources(self):
        root = make_repo()
        (root / "vendors/acme-roofing.md").write_text("---\ntype: tool\nname: Acme\nupdated: 2026-01-01\n---\n")
        (root / "facts/2023.csv").write_text("id,date,time,person,domain,kind,entity,summary,value,amount,due,contact,link,source\nF000001,2023-4-4,,Bob,moon,k,,s,,,,,vendors/none,\n")
        found = check.run(make_index(root))
        for name in ("fact date is not YYYY-MM-DD", "fact person is not a known person", "fact domain is not a known domain", "fact links to a missing record", "record type does not match its folder", "fact has no source"):
            self.assertEqual(len(found[name]), 1, name)


class GraphChecks(unittest.TestCase):
    def test_reports_broken_organization_and_document_references(self):
        root = make_repo()
        (root / "organizations/names.csv").write_text("name,org,unit\nMain Street Orthodontics,gone,\nAcme Roofing,,place\n")
        (root / "organizations/organizations.csv").write_text("id,name,kind,record\nacme-roofing,Acme Roofing,contractor,vendors/none\n")
        (root / "documents/sources.csv").write_text("path,source\ndocuments/archive/roof/2023/lost.pdf,mail:10\n")
        (root / "property/roof.md").write_text("---\ntype: property\nname: Roof\nupdated: 2026-01-02\n---\n\nSee `documents/archive/roof/2023/lost.pdf` and `documents/archive/roof/`.\n")
        found = check.run(make_index(root))
        self.assertEqual(found["name maps to a missing organization"], ["Main Street Orthodontics gone"])
        self.assertEqual(found["organization points to a missing record"], ["acme-roofing vendors/none"])
        self.assertEqual(found["document source names a missing file"], ["documents/archive/roof/2023/lost.pdf"])
        self.assertEqual(found["record names a missing document"], ["property/roof documents/archive/roof/2023/lost.pdf"])
        self.assertEqual(found["entity name has no organization entry"], [])


class Intake(unittest.TestCase):
    def test_pull_saves_items_and_documents_and_resolve_posts_the_status(self):
        import io, json, tempfile
        from unittest import mock
        from kb import intake
        calls = []
        replies = {"/api/v1/intake/pending": json.dumps([{"id": 7, "kind": "document", "filename": "q.pdf", "fact": {}}, {"id": 8, "kind": "fact", "fact": {"summary": "s"}}]).encode(),
                   "/api/v1/intake/7/content": b"PDF", "/api/v1/intake/8/resolve": b'{"status": "accepted"}'}
        def opener(req):
            calls.append((req.get_method(), req.full_url, req.get_header("Authorization"), req.data))
            reply = io.BytesIO(replies[req.full_url.replace(intake.SERVER, "")])
            reply.__enter__ = lambda: reply; reply.__exit__ = lambda *a: None
            return reply
        with tempfile.TemporaryDirectory() as root:
            token = Path(root) / "token"
            token.write_text("secret\n")
            with mock.patch.object(intake, "TOKEN_FILE", token), mock.patch.object(intake, "REPO", Path(root)):
                folder, items = intake.pull("2026-11-16", opener=opener)
                self.assertEqual((folder / "7-q.pdf").read_bytes(), b"PDF")
                self.assertEqual(len(json.loads((folder / "items.json").read_text())), 2)
                self.assertEqual(intake.resolve(8, "accepted", "F000001", opener=opener), {"status": "accepted"})
        self.assertEqual(calls[0][2], "Bearer secret")
        self.assertEqual(json.loads(calls[-1][3]), {"status": "accepted", "outcome": "F000001"})


class MailSave(unittest.TestCase):
    def test_saves_the_body_and_fills_an_attachment_from_the_attachments_folder(self):
        import tempfile
        from kb.sources import mail
        raw = (b"From: a@b.c\nSubject: Receipt\nMIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=X\n\n"
               b"--X\nContent-Type: text/plain\n\nPaid $5\n--X\nContent-Type: application/pdf\nContent-Disposition: attachment; filename=r.pdf\n\n\n--X--\n")
        with tempfile.TemporaryDirectory() as root:
            store = Path(root) / "V10/acct/INBOX.mbox/U/Data"
            (store / "Messages").mkdir(parents=True)
            (store / "Messages/42.partial.emlx").write_bytes(str(len(raw)).encode() + b"\n" + raw)
            (store / "Attachments/42/2").mkdir(parents=True)
            (store / "Attachments/42/2/r.pdf").write_bytes(b"%PDF real")
            eml, files = mail.save_mail(42, Path(root) / "out", mail=Path(root) / "V10")
            self.assertEqual(Path(eml).read_bytes(), raw)
            self.assertEqual(Path(files[0]).read_bytes(), b"%PDF real")
            self.assertEqual(mail.save_mail(7, Path(root) / "out", mail=Path(root) / "V10"), (None, []))

    def test_writes_the_text_of_a_word_attachment_next_to_it(self):
        import tempfile, zipfile
        from kb.sources import mail
        with tempfile.TemporaryDirectory() as root:
            doc = Path(root) / "note.docx"
            with zipfile.ZipFile(doc, "w") as archive:
                archive.writestr("word/document.xml", "<w:t>Eye check &amp; road test on May 7</w:t>")
            mail.write_attachment_texts([str(doc), str(Path(root) / "missing.pdf")])
            self.assertEqual(Path(f"{doc}.txt").read_text(), "Eye check & road test on May 7")
            self.assertFalse(Path(root, "missing.pdf.txt").exists())


class Edits(unittest.TestCase):
    def test_adds_a_valid_fact_once(self):
        root = make_repo()
        row = {"date": "2025-05-05", "person": "Sam", "domain": "health", "kind": "appointment", "summary": "Eye exam", "source": "mail:99", "link": "vendors/acme-roofing"}
        added, skipped = edit.add_facts([row], root)
        self.assertEqual((added[0]["id"], skipped), ("F000004", []))
        self.assertEqual(edit.add_facts([row], root)[0], [])
        self.assertEqual(len(read_facts(root / "facts")), 4)

    def test_refuses_an_invalid_fact(self):
        bad = new_fact(date="2025-13-01", person="Bob", domain="moon", kind="", summary="", source="memory", link="vendors/none", amount="lots")
        self.assertEqual(len(edit.problems(bad, make_repo())), 7)
        with self.assertRaises(ValueError):
            edit.add_facts([{"date": "x"}], make_repo())
        with self.assertRaises(ValueError):
            new_fact(color="red")

    def test_first_id_in_an_empty_table(self):
        self.assertEqual(next_id([]), "F000001")


if __name__ == "__main__":
    unittest.main()


class InfiniteCampusChangesTest(unittest.TestCase):
    def test_reports_only_new_or_changed_items(self):
        from kb.sources.infinite_campus import changes
        record = {"student": "Riley", "grades": [{"course": "Sociology Honors", "term": "Q2 Term Grade", "percent": 47.36}],
                  "assignments": [{"id": 1, "title": "Genie", "score": "0"}], "attendance": []}
        first, seen = changes([record], {})
        self.assertEqual(["grade", "assignment"], [row["kind"] for row in first])
        record["assignments"][0]["score"] = "80"
        second, _ = changes([record], seen)
        self.assertEqual([("assignment", "80")], [(row["kind"], row["score"]) for row in second])


class AgentCalendarTest(unittest.TestCase):
    def test_writes_once_per_change(self):
        import datetime, tempfile, sqlite3
        from pathlib import Path
        from kb import agent_calendar
        folder = Path(tempfile.mkdtemp())
        index = folder / "kb.sqlite"
        con = sqlite3.connect(index)
        con.execute("create table facts (id, date, time, person, kind, entity, summary, source, due)")
        day = datetime.date.today().isoformat()
        con.execute("insert into facts values ('F1', ?, '08:00', 'Jordan', 'assignment', 'Math 6 Plus', 'Unit 7.1 Quiz', 'canvas:Jordan:assignment:1', '')", (day,))
        con.execute("insert into facts values ('F2', ?, '', 'Riley', 'grade', 'Sociology Honors', 'Unit Three Test 0/100', 'file:x', '')", (day,))
        con.commit()
        calls = []
        state = folder / "state.json"
        self.assertEqual(1, agent_calendar.sync(index, state, lambda *a, **k: calls.append(k["input"]), judge=lambda rows: [False] * len(rows)))
        self.assertIn("Jordan: Due Unit 7.1 Quiz (Math 6 Plus)", calls[0])
        self.assertNotIn("Unit Three Test", calls[0])
        self.assertEqual(0, agent_calendar.sync(index, state, lambda *a, **k: calls.append(k["input"]), judge=lambda rows: [False] * len(rows)))
        self.assertEqual(1, len(calls))

    def test_includes_expiry_and_social_dates(self):
        import datetime, tempfile, sqlite3
        from pathlib import Path
        from kb import agent_calendar
        index = Path(tempfile.mkdtemp()) / "kb.sqlite"
        con = sqlite3.connect(index)
        con.execute("create table facts (id, date, time, person, kind, entity, summary, source, due)")
        con.execute("insert into facts values ('F1', '2033-03-04', '', 'Sam', 'license', 'NCDMV', 'Driver license, class C', 'file:x', '')")
        con.execute("insert into facts values ('F2', '2026-12-16', '19:00', 'household', 'social', 'Club', 'Sammy Obeid at Club', 'mail:1', '')")
        con.execute("insert into facts values ('F3', '2026-12-16', '', 'Riley', 'conversation', 'Park', 'Riley emailed', 'mail:2', '')")
        con.commit()
        con.execute("insert into facts values ('F4', '2026-12-20', '', 'Biscuit', 'checkup', 'Vet', 'Biscuit annual exam at the vet', 'mail:3', '')")
        con.commit()
        with fake_jev(lambda state, q: {"event": {"noul": 0.9 if "annual exam" in state["fact"] else 0.1}}) as stub:
            titles = [e["title"] for e in agent_calendar.wanted(index, datetime.date(2026, 11, 18))]
            again = agent_calendar.wanted(index, datetime.date(2026, 11, 18))
        self.assertEqual(["Household: Sammy Obeid at Club", "Biscuit: Biscuit annual exam at the vet", "Sam: Ends: Driver license, class C"], titles)
        self.assertEqual(2, len(stub.calls))
        self.assertEqual(3, len(again))


class SecretScanTest(unittest.TestCase):
    def test_moves_secret_files_into_the_vault_and_repoints_sources(self):
        import tempfile
        from pathlib import Path
        from kb import secret_scan
        from kb.facts import read_facts, write_facts
        root = Path(tempfile.mkdtemp())
        archive = root / "documents/archive/slack/2026"
        archive.mkdir(parents=True)
        (archive / "keys.png").write_bytes(b"png")
        (archive / "keys.png.txt").write_text("my wifi password is hunter2")
        (archive / "menu.txt").write_text("Tacos on Tuesday")
        (archive / "token.md").write_text("token sk-abcdefghijklmnopqrstuvwxyz123")
        (archive / "photo.jpg").write_bytes(b"jpg")
        (root / "documents/sources.csv").write_text("path,source\ndocuments/archive/slack/2026/keys.png,slack:x:1\n")
        fact = {"id": "F1", "date": "2026-01-01", "time": "", "person": "Sam", "domain": "home", "kind": "note", "entity": "", "summary": "Wifi",
                "value": "", "amount": "", "due": "", "contact": "", "link": "", "source": "file:documents/archive/slack/2026/keys.png"}
        write_facts([fact], root / "facts")
        names = ["documents/archive/slack/2026/" + n for n in ("keys.png", "keys.png.txt", "menu.txt", "token.md", "photo.jpg")] + ["facts/2026.csv"]
        with fake_jev(lambda state, q: {"secret": {"noul": 0.95 if "password" in state["text"] else 0.02}}):
            hits, unread = secret_scan.flagged(names, root)
        self.assertEqual(["documents/archive/slack/2026/keys.png", "documents/archive/slack/2026/token.md"], hits)
        self.assertEqual(["documents/archive/slack/2026/photo.jpg"], unread)
        secret_scan.move(hits, root)
        self.assertTrue((root / "vault/archive/slack/2026/keys.png.txt").exists())
        self.assertFalse((archive / "keys.png").exists())
        self.assertTrue((archive / "menu.txt").exists())
        self.assertIn("vault/archive/slack/2026/keys.png", (root / "documents/sources.csv").read_text())
        self.assertEqual("file:vault/archive/slack/2026/keys.png", read_facts(root / "facts")[0]["source"])


class FactAuditTest(unittest.TestCase):
    def test_reports_confident_disagreements_only(self):
        from kb import fact_audit
        facts = [{"id": "F1", "date": "2026-01-01", "kind": "visit", "entity": "Pine Pediatrics", "summary": "Jordan well check", "domain": "home", "person": "Riley"},
                 {"id": "F2", "date": "2026-01-02", "kind": "bill", "entity": "City Power & Light", "summary": "Electric bill", "domain": "finance", "person": "household"}]

        def answer(state, q):
            if "well check" in state["fact"]:
                return {"domain": {"choice": "health", "confidence": 0.97}, "person": {"choice": "Jordan", "confidence": 0.93}}
            return {"domain": {"choice": "home", "confidence": 0.6}, "person": {"choice": "Sam", "confidence": 0.99}}

        with fake_jev(answer):
            found = fact_audit.disagreements(facts)
        self.assertEqual([("F1", "domain", "health"), ("F1", "person", "Jordan")], [(d["id"], d["field"], d["jev"]) for d in found])


class SlackTest(unittest.TestCase):
    def test_collects_only_new_messages(self):
        import json
        from unittest import mock
        from kb.sources import slack
        answers = {
            "auth.test": {"url": "https://maplelane.slack.com/"},
            "users.list": {"members": [{"id": "U1", "real_name": "Alex"}]},
            "users.conversations": {"channels": [{"id": "C1", "name": "family"}]},
            "conversations.history": {"messages": [{"ts": "200.0", "user": "U1", "text": "Dentist moved to Friday"},
                                                    {"ts": "100.0", "user": "U1", "text": "old", "latest_reply": "300.0"}]},
            "conversations.replies": {"messages": [{"ts": "100.0", "text": "old"}, {"ts": "300.0", "user": "U1", "text": "late reply", "thread_ts": "100.0"}]},
        }

        def fake(request, timeout):
            method = request.full_url.split("/api/")[1].split("?")[0]
            body = mock.MagicMock()
            body.__enter__.return_value.read.return_value = json.dumps({"ok": True, **answers[method]}).encode()
            return body

        with mock.patch("urllib.request.urlopen", fake):
            rows, seen = slack.collect({"C1": "100.0"}, secret="x")
        self.assertEqual(["Dentist moved to Friday", "late reply"], [r["text"] for r in rows])
        self.assertEqual("Alex", rows[0]["from"])
        self.assertEqual("https://maplelane.slack.com/archives/C1/p2000", rows[0]["link"])
        self.assertEqual({"C1": "300.0"}, seen)


class SlackExportTest(unittest.TestCase):
    def test_groups_threads_and_gaps(self):
        from kb import slack_export
        messages = [{"ts": "0.0", "text": "a", "reply_count": 1}, {"ts": "60.0", "thread_ts": "0.0", "text": "reply"},
                    {"ts": "30.0", "text": "b"}, {"ts": "20000.0", "text": "c"}]
        groups = slack_export.sessions(sorted(messages, key=lambda m: float(m["ts"])))
        self.assertEqual([["a", "reply", "b"], ["c"]], [[m["text"] for m in g] for g in groups])
        self.assertEqual(2, len(list(slack_export.chunks(groups, size=3))))

    def test_finds_every_url(self):
        from kb import slack_export
        message = {"text": "see <https://a.com/x|A> and https://b.com/y.", "attachments": [{"from_url": "https://c.com"}]}
        self.assertEqual(["https://a.com/x", "https://b.com/y", "https://c.com"], slack_export.urls(message))


class SlackTranscriptTest(unittest.TestCase):
    def test_shows_bot_posted_shares(self):
        from kb import slack_export
        message = {"ts": "0.0", "subtype": "bot_message", "text": "", "attachments": [{"fallback": "@alexlane: Please be scalable", "author_name": "Alex Lane"}]}
        text = slack_export.transcript("family-matters", [[message]], {}, {})
        self.assertIn("Alex Lane (ts 0.0): [shared: @alexlane: Please be scalable]", text)


class DigestTest(unittest.TestCase):
    def test_lists_today_week_and_only_new_changes(self):
        import datetime
        from kb import digest
        today = datetime.date(2026, 11, 17)
        row = {"id": "F1", "date": "2026-11-17", "person": "Riley", "domain": "school", "kind": "grade", "summary": "Unit Three Test 0/100", "value": "0/100", "source": "file:x"}
        quiet = dict(row, id="F2", summary="Quiz 100/100", value="100/100")
        upcoming = [{"day": "2026-11-17", "time": "08:00", "title": "Jordan: Due Unit 7.1 Quiz (Math 6 Plus)"}, {"day": "2026-11-20", "time": "", "title": "Jordan: Due Study Guide"}]
        first = digest.build({"F1": row, "F2": quiet}, {}, today, upcoming)
        self.assertIn("08:00: Jordan: Due Unit 7.1 Quiz", first)
        self.assertIn("11-20: Jordan: Due Study Guide", first)
        self.assertNotIn("New or changed", first)
        state = {"facts": {"F2": digest.digest_of(quiet), "F1": "old"}}
        later = digest.build({"F1": row, "F2": quiet}, state, today, [])
        self.assertIn("Riley: Unit Three Test 0/100 (F1)", later)
        self.assertNotIn("Quiz 100/100", later)


class WeekTest(unittest.TestCase):
    def test_flags_kid_outings_away_from_school(self):
        import argparse, contextlib, io, sqlite3
        from kb import commands
        con = sqlite3.connect(":memory:")
        con.execute("create table facts (id, date, time, person, domain, kind, entity, summary, due, value)")
        con.execute("insert into facts values ('F1', '2026-11-18', '17:30', 'Jordan', 'activities', 'practice', 'Soccer', 'Soccer practice', '', '')")
        con.execute("insert into facts values ('F2', '2026-11-18', '', 'Riley', 'school', 'event', 'Westbrook High School', 'Spirit day', '', '')")
        con.execute("insert into facts values ('F3', '2026-11-18', '', 'Sam', 'job', 'meeting', 'Acme', 'Standup', '', '')")
        con.execute("insert into facts values ('F4', '2026-11-04', '18:00', 'Riley', 'activities', 'event', 'Studio', 'Riley with Grace', '', 'repeats on 3 dates: 2026-11-04 2026-11-11 2026-11-18')")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            commands.week(con, argparse.Namespace(start="2026-11-18", days=1, person=None, json=False))
        self.assertIn("Soccer practice  [needs a driver]", out.getvalue())
        self.assertIn("Spirit day  (F2)", out.getvalue())
        self.assertNotIn("Standup", out.getvalue())
        self.assertEqual(1, out.getvalue().count("Riley with Grace"))


class RecurringTest(unittest.TestCase):
    def test_folds_a_series_into_one_fact(self):
        from kb import recurring
        base = {"time": "12:05", "person": "Sam", "domain": "job", "kind": "meeting", "entity": "Acme", "summary": "Deep Dives",
                "value": "", "amount": "", "due": "", "contact": "", "link": "", "source": "calendar:work"}
        facts = [dict(base, id=f"F{n}", date=d) for n, d in ((3, "2027-06-17"), (1, "2027-06-15"), (2, "2027-06-22"))]
        facts.append(dict(base, id="F9", date="2027-06-15", summary="Toolsday"))
        kept, merged = recurring.collapse(facts)
        self.assertEqual(["F1", "F9"], sorted(f["id"] for f in kept))
        self.assertEqual("repeats on 3 dates: 2027-06-15 2027-06-17 2027-06-22", kept[0]["value"] if kept[0]["id"] == "F1" else kept[1]["value"])
        self.assertEqual({"F2": "F1", "F3": "F1"}, merged)
        again, folded = recurring.collapse(kept + [dict(base, id="F5", date="2027-06-29")])
        self.assertEqual({"F5": "F1"}, folded)
        self.assertTrue(next(f for f in again if f["id"] == "F1")["value"].startswith("repeats on 4 dates"))

    def test_folds_identical_mail_facts_and_keeps_every_source(self):
        from kb import recurring
        base = {"time": "", "person": "Sam", "domain": "finance", "kind": "statement", "entity": "Chase", "summary": "Credit card statement available",
                "value": "", "amount": "", "due": "", "contact": "", "link": ""}
        facts = [dict(base, id="F1", date="2026-01-05", source="mail:1"), dict(base, id="F2", date="2026-02-05", source="mail:2"),
                 dict(base, id="F3", date="2026-03-05", source="mail:3", value="score 9")]
        kept, merged = recurring.collapse(facts)
        self.assertEqual({"F2": "F1"}, merged)
        self.assertEqual("mail:1 mail:2", kept[0]["source"])
        self.assertEqual("score 9", kept[1]["value"])


class TriageTest(unittest.TestCase):
    def test_tags_and_sorts_household_first(self):
        from kb import triage
        rows = [{"id": 1, "text": "lol", "handle": "+1"}, {"id": 2, "text": "dentist friday", "handle": "+2"}]

        def ask(states):
            return [{"domain": {"choice": "health" if "dentist" in s["message"] else "other", "confidence": 1}, "household": {"noul": 0.9 if "dentist" in s["message"] else 0.05}} for s in states]

        found = triage.tag(rows, ask)
        self.assertEqual([2, 1], [r["id"] for r in found])
        self.assertEqual({"domain": "health", "household": 0.9}, found[0]["jev"])
        self.assertEqual({"high": 1, "low": 1, "total": 2}, triage.counts(found))


class DocTest(unittest.TestCase):
    def test_excerpt_by_type(self):
        import tempfile
        from kb import doc_text
        folder = Path(tempfile.mkdtemp())
        (folder / "a.html").write_text("<style>x{}</style><p>Roof&amp;gutter</p>" + "y" * 5000)
        (folder / "b.bin").write_bytes(b"\x00")
        (folder / "c.pdf").write_bytes(b"%PDF")
        self.assertEqual(4000, len(doc_text.excerpt(folder / "a.html")))
        self.assertTrue(doc_text.excerpt(folder / "a.html").startswith("Roof&gutter"))
        self.assertEqual("", doc_text.excerpt(folder / "b.bin"))
        ran = []
        run = lambda cmd, **k: ran.append(cmd) or type("R", (), {"stdout": " lease  text "})()
        self.assertEqual("lease text", doc_text.excerpt(folder / "c.pdf", run=run))
        self.assertEqual("pdftotext", ran[0][0])

    def test_triage_maps_answers(self):
        from kb import doc_area
        found = doc_area.triage([{"id": 7, "path": "a.txt", "ext": ".txt", "text": "w2"}], lambda states: [{"area": {"choice": "household", "confidence": 0.9}}])
        self.assertEqual([{"id": 7, "area": "household", "confidence": 0.9}], found)
        self.assertEqual([], doc_area.triage([]))


class DupesTest(unittest.TestCase):
    def facts(self):
        base = {"date": "2026-01-01", "person": "Riley", "domain": "health", "kind": "visit", "entity": "Dr Lee", "time": "", "value": "", "amount": "", "due": "", "contact": "", "link": ""}
        return [{**base, "id": "F000002", "summary": "Dentist visit cleaning", "source": "mail:2 file:x", "contact": "555"},
                {**base, "id": "F000001", "summary": "Dentist visit", "source": "mail:1 file:x", "link": "vendors/a"},
                {**base, "id": "F000003", "summary": "Soccer", "entity": "Club", "kind": "game", "source": "mail:3"}]

    def test_finds_and_applies(self):
        from kb import dupes
        from kb.facts import write_facts
        facts = self.facts()
        self.assertEqual(1, len(dupes.candidates(facts)))
        found = dupes.find(facts, lambda states: [{"noul": {"noul": 0.95}} for _ in states])
        self.assertEqual([("F000001", "F000002")], [(d["keep"], d["drop"]) for d in found])
        self.assertEqual([], dupes.find(facts, lambda states: [{"noul": {"noul": 0.5}} for _ in states]))
        import tempfile
        root = Path(tempfile.mkdtemp())
        (root / "documents").mkdir()
        (root / "documents/fact-links.csv").write_text("fact,path\nF000001,p.pdf\nF000002,p.pdf\nF000002,q.pdf\n")
        (root / "notes.md").write_text("see F000002 and F000003\n")
        write_facts(facts, root / "facts")
        dupes.apply(found, root)
        left = read_facts(root / "facts")
        self.assertEqual(["F000001", "F000003"], [f["id"] for f in left])
        self.assertEqual("mail:1 file:x mail:2", left[0]["source"])
        self.assertEqual("555", left[0]["contact"])
        self.assertEqual("Dentist visit cleaning", left[0]["summary"])
        self.assertEqual("vendors/a", left[0]["link"])
        self.assertEqual("fact,path\nF000001,p.pdf\nF000001,q.pdf\n", (root / "documents/fact-links.csv").read_text())
        self.assertEqual("see F000001 and F000003\n", (root / "notes.md").read_text())


class RecordFoldersTest(unittest.TestCase):
    def test_extra_record_folders_come_from_the_config(self):
        import os, subprocess, sys, tempfile
        folder = Path(tempfile.mkdtemp())
        (folder / "household.toml").write_text('[household]\nname = "Test"\n[records]\nextra = ["hot-tub", "gear"]\n')
        code = "from kb.schema import ENTITY_FOLDERS as E; print(E['hot-tub'], E['gear'], E['vendors'])"
        env = {**os.environ, "HOUSEHOLD_CONFIG": str(folder / "household.toml"), "HOME": str(folder)}
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=Path(__file__).resolve().parent.parent)
        self.assertEqual("hot-tub gear vendor", out.stdout.strip(), out.stderr)

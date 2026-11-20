import base64
import io
import json
import tempfile
import unittest
from pathlib import Path

from kb.sources import gmail

RAW = b"From: Oak Hill Animal Hospital <vet@example.com>\r\nSubject: Reminder\r\nContent-Type: text/plain\r\n\r\nBiscuit is due Friday at 4:00 PM.\r\n"


def opener_for(replies, seen):
    def opener(request):
        url = request.full_url
        seen.append(url)
        for key, body in replies.items():
            if key in url:
                return io.BytesIO(json.dumps(body).encode())
        raise AssertionError(url)
    return opener


class GmailTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.login = self.root / "gmail.json"
        self.login.write_text(json.dumps({"client_id": "c", "client_secret": "s", "refresh_token": "r"}))

    def test_first_run_starts_the_cursor_at_now(self):
        seen = []
        opener = opener_for({"oauth2": {"access_token": "t"}, "/profile": {"historyId": "900"}}, seen)
        rows, cursor = gmail.collect({}, self.root, opener=opener, login=self.login)
        self.assertEqual(([], {"history_id": "900"}), (rows, cursor))

    def test_saves_each_new_message(self):
        seen = []
        replies = {"oauth2": {"access_token": "t"}, "/history": {"history": [{"messagesAdded": [{"message": {"id": "m1"}}]}], "historyId": "950"},
                   "/messages/m1": {"raw": base64.urlsafe_b64encode(RAW).decode()}}
        rows, cursor = gmail.collect({"history_id": "900"}, self.root, opener=opener_for(replies, seen), login=self.login)
        self.assertEqual({"history_id": "950"}, cursor)
        self.assertEqual("gmail-m1", rows[0]["id"])
        self.assertEqual("Reminder", rows[0]["subject"])
        self.assertIn("Biscuit is due Friday", (self.root / "gmail-m1/body.txt").read_text())

    def test_wrong_cursor_fails_the_negative_control(self):
        seen = []
        replies = {"oauth2": {"access_token": "t"}, "/history": {"history": [], "historyId": "901"}}
        rows, cursor = gmail.collect({"history_id": "900"}, self.root, opener=opener_for(replies, seen), login=self.login)
        self.assertEqual([], rows)
        self.assertNotEqual({"history_id": "900"}, cursor)


if __name__ == "__main__":
    unittest.main()

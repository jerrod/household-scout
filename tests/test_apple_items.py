import json
import unittest
from types import SimpleNamespace

from kb import ingest, mask

NOTES = [
    {"account": "iCloud", "folder": "Notes", "id": "p1", "title": "Garage", "created": "2026-01-01T00:00:00Z", "modified": "2026-01-02T00:00:00Z",
     "locked": False, "body": "Door code is 4417\nFilter size 20x25x1\nkey sk-abcdefghijklmnopqrstuvwxyz"},
    {"account": "iCloud", "folder": "Notes", "id": "p2", "title": "Old", "created": "2025-01-01T00:00:00Z", "modified": "2025-01-01T00:00:00Z",
     "locked": False, "body": "old"},
]


def run_with(rows):
    return lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(rows))


class AppleItemsTest(unittest.TestCase):
    def test_reads_only_items_changed_since_the_watermark_and_masks_secrets(self):
        judge = lambda lines: ["code is" in line for line in lines]
        rows, until = ingest.apple_items("notes", "2025-06-01", {"notes": {}}, run=run_with(NOTES), judge=judge)
        self.assertEqual(["p1"], [row["id"] for row in rows])
        self.assertEqual("2026-01-02T00:00:00Z", until)
        self.assertEqual("[secret]\nFilter size 20x25x1\nkey [secret]", rows[0]["body"])

    def test_skips_a_source_missing_from_the_config(self):
        self.assertEqual(([], "x"), ingest.apple_items("reminders", "x", {}, run=run_with(NOTES)))

    def test_a_reader_failure_keeps_the_watermark(self):
        def broken(*args, **kwargs):
            raise OSError("Notes is not running")
        self.assertEqual(([], "2025"), ingest.apple_items("notes", "2025", {"notes": {}}, run=broken))

    def test_mask_leaves_clean_text_alone(self):
        rows = mask.mask_rows([{"title": "Soccer", "body": "Practice at 5"}], ("title", "body"), judge=lambda lines: [False] * len(lines))
        self.assertEqual([{"title": "Soccer", "body": "Practice at 5"}], rows)

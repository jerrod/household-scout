import unittest

from kb import ingest


class TagMailTest(unittest.TestCase):
    def test_tags_stay_on_the_rows_written_last(self):
        mail = [{"id": 1}, {"id": 2}]
        ingest.tag_mail(mail, {1: {"domain": "school"}}, {2: {"amount": 5}})
        self.assertEqual({"domain": "school"}, mail[0]["jev"])
        self.assertIsNone(mail[0]["record"])
        self.assertEqual({"amount": 5}, mail[1]["record"])


if __name__ == "__main__":
    unittest.main()

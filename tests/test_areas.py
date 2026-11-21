import unittest

from kb import areas


class AreasTest(unittest.TestCase):
    def test_one_area_list_serves_every_source(self):
        config = {"home": {"about": "The house.", "kinds": {"pool": "The pool."}}, "health": {"about": "Doctors.", "vault": True}}
        self.assertEqual({"home": "The house.", "health": "Doctors.", "other": "Fits no area."}, areas.choices(config))
        self.assertEqual({"home": {"pool": "The pool."}}, areas.kinds(config))
        self.assertEqual({"health"}, areas.vault(config))


if __name__ == "__main__":
    unittest.main()

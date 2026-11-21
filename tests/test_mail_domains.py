import unittest

from kb import mail_domains


class MailDomainsTest(unittest.TestCase):
    def test_household_adds_replaces_and_removes_categories(self):
        config = {"mail": {"domains": {"pool": "The pool.", "pets": "", "home": "The house."}, "subtypes": {"pool": {"service": "A visit."}, "pets": {"vet": ""}}}}
        found = mail_domains.domains(config)
        self.assertEqual("The pool.", found["pool"])
        self.assertEqual("The house.", found["home"])
        self.assertNotIn("pets", found)
        self.assertEqual("other", list(found)[-1])
        kinds = mail_domains.subtypes(config)
        self.assertEqual({"service": "A visit."}, kinds["pool"])
        self.assertEqual({"pet_supplies": "Pet food or supplies."}, kinds["pets"])

    def test_defaults_without_config(self):
        self.assertEqual(mail_domains.DEFAULT_DOMAINS, mail_domains.domains({}))


if __name__ == "__main__":
    unittest.main()

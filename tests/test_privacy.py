import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def terms():
    text = os.environ.get("PRIVACY_TERMS") or ((ROOT / ".privacy-terms").read_text() if (ROOT / ".privacy-terms").exists() else "")
    return [t.strip() for t in text.splitlines() if t.strip()]


def shipped_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / f for f in out.splitlines() if (ROOT / f).is_file()]


def hits(words, files):
    pattern = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(w) for w in words) + r")(?![A-Za-z0-9])", re.I)
    found = []
    for path in files:
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            match = pattern.search(line)
            if match:
                found.append(f"{path.relative_to(ROOT)}:{number}: {match.group(0)}")
    return found


class PrivacyTest(unittest.TestCase):
    def test_no_private_term_ships(self):
        words = terms()
        if not words:
            if os.environ.get("CI"):
                self.fail("set the PRIVACY_TERMS secret")
            self.skipTest("no .privacy-terms file")
        self.assertEqual([], hits(words, shipped_files()))

    def test_scanner_catches_a_planted_term(self):
        planted = ROOT / "tests" / ".planted"
        planted.write_text("call Zebediah tomorrow\n")
        try:
            self.assertEqual(1, len(hits(["zebediah"], [planted])))
        finally:
            planted.unlink()


if __name__ == "__main__":
    unittest.main()

import ast
import unittest
from pathlib import Path

KB = Path(__file__).resolve().parent.parent / "kb"


class ScriptImportTest(unittest.TestCase):
    def test_scripts_set_the_path_before_importing_kb(self):
        for path in KB.glob("*.py"):
            text = path.read_text()
            if "__main__" not in text:
                continue
            tree = ast.parse(text)
            imports = [n.lineno for n in tree.body if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "kb"]
            paths = [n.lineno for n in tree.body if "sys.path" in ast.unparse(n)]
            if imports:
                self.assertTrue(paths and min(paths) < min(imports), path.name)


if __name__ == "__main__":
    unittest.main()

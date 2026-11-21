import html
import re
import subprocess

TEXT = {".txt", ".md", ".csv", ".eml", ".html", ".htm"}
LIMIT = 4000
READ_BYTES = 200_000


def excerpt(path, ext=None, run=subprocess.run):
    ext = (ext or str(path)[str(path).rfind("."):]).lower()
    if ext == ".pdf":
        try:
            text = run(["pdftotext", "-l", "5", str(path), "-"], capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
    elif ext in TEXT:
        try:
            with open(path, "rb") as handle:
                text = handle.read(READ_BYTES).decode("utf-8", "replace")
        except OSError:
            return ""
        if ext in (".html", ".htm"):
            text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(style|script).*?</\1>", " ", text)))
    else:
        return ""
    return re.sub(r"\s+", " ", text).strip()[:LIMIT]

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FACTS_DIR = REPO / "facts"
DATABASE = REPO / ".kb" / "kb.sqlite"

FACT_COLUMNS = ["id", "date", "time", "person", "domain", "kind", "entity", "summary", "value", "amount", "due", "contact", "link", "source"]

from kb.household import AREAS, FAMILY, PETS, RECORDS_EXTRA  # noqa: E402
PEOPLE = FAMILY + PETS + ["household", "other", ""]

DOMAINS = list(AREAS)

ENTITY_FOLDERS = {
    "property": "property",
    "appliances": "appliance",
    "vehicles": "vehicle",
    "vendors": "vendor",
    "work": "work",
    "devices": "device",
    "people": "person",
    "policies": "policy",
    **{folder: folder for folder in RECORDS_EXTRA},
}

PRIVATE_FOLDERS = {"vault", "secrets"}
SOURCE_PREFIXES = ("mail:", "text:", "window:", "calendar:", "file:", "person:", "canvas:", "slack:")

import os
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def config_path():
    chosen = os.environ.get("HOUSEHOLD_CONFIG")
    if chosen:
        return Path(chosen)
    own = REPO / "household.toml"
    return own if own.exists() else REPO / "sample/household.toml"


CONFIG = tomllib.loads(config_path().read_text())
NAME = CONFIG["household"]["name"]
TIMEZONE = CONFIG["household"].get("timezone", "UTC")
STATE = Path(os.path.expanduser(CONFIG["household"].get("state_dir", "~/.config/household-scout")))
PEOPLE = CONFIG.get("people", [])
FAMILY = [p["name"] for p in PEOPLE if p.get("role") != "pet"]
PETS = [p["name"] for p in PEOPLE if p.get("role") == "pet"]
KIDS = [p["name"] for p in PEOPLE if p.get("role") == "child"]
AREAS = CONFIG.get("areas", {})
SOURCES = CONFIG.get("sources", {})
RECORDS_EXTRA = CONFIG.get("records", {}).get("extra", [])


def source(name):
    return SOURCES.get(name, {})

"""Kill switch check — if logs/KILL exists, close all positions and halt."""
from pathlib import Path
from config import LOG_DIR

KILL_FILE = Path(LOG_DIR) / "KILL"


def is_active() -> bool:
    return KILL_FILE.exists()


def activate():
    KILL_FILE.parent.mkdir(exist_ok=True)
    KILL_FILE.write_text("activated at " + __import__("datetime").datetime.utcnow().isoformat())


def deactivate():
    if KILL_FILE.exists():
        KILL_FILE.unlink()


if __name__ == "__main__":
    print(f"Kill switch active: {is_active()}")

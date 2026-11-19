import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent / "data" / "offline"
ROOT.mkdir(parents=True, exist_ok=True)


def mirror(filename, record):
    path = ROOT / filename
    try:
        existing = json.loads(path.read_text()) if path.exists() else []
    except Exception:
        existing = []
    record = {**record, "_mirrored_at": datetime.now(timezone.utc).isoformat()}
    existing.append(record)
    path.write_text(json.dumps(existing, indent=2, default=str))
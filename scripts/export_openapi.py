"""Write docs/openapi.json from the current FastAPI application."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "openapi.json"


def export_openapi(path: Path = OUTPUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    written = export_openapi()
    print(written.relative_to(ROOT))

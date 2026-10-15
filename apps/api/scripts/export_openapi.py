"""Write the OpenAPI document used to generate the typed web client.

Run from apps/api:  uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

OUT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"


def main() -> None:
    app = create_app(Settings(env="test", auth_mode="dev"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

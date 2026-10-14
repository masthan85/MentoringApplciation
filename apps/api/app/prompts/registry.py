"""Versioned prompt templates.

Prompts are files named ``<name>.v<N>.md`` next to this module. ``manifest.json``
records the SHA-256 of each file, and a test fails when a prompt changes without
the manifest being regenerated, so every prompt change is deliberate and visible
in review. (Phase 3 adds the evaluation suite that gates these changes.)
"""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent
MANIFEST = PROMPT_DIR / "manifest.json"
_NAME = re.compile(r"^(?P<name>[a-z_]+)\.v(?P<version>\d+)\.md$")


def _files() -> dict[str, Path]:
    return {p.name: p for p in sorted(PROMPT_DIR.glob("*.md"))}


@lru_cache
def load(name: str, version: int) -> str:
    return (PROMPT_DIR / f"{name}.v{version}.md").read_text().strip()


def version_label(name: str, version: int) -> str:
    return f"{name}.v{version}"


def compute_manifest() -> dict[str, str]:
    return {
        filename: hashlib.sha256(path.read_bytes()).hexdigest()
        for filename, path in _files().items()
    }


def write_manifest() -> None:
    MANIFEST.write_text(json.dumps(compute_manifest(), indent=2, sort_keys=True) + "\n")


def read_manifest() -> dict[str, str]:
    result: dict[str, str] = json.loads(MANIFEST.read_text())
    return result

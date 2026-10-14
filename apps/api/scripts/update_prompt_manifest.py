"""Regenerate app/prompts/manifest.json after a deliberate prompt change.

Run from apps/api:  uv run python scripts/update_prompt_manifest.py
Then run the evaluation suite (once it exists) before merging.
"""

from app.prompts.registry import write_manifest

if __name__ == "__main__":
    write_manifest()
    print("manifest updated")

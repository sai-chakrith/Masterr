"""Whole-topic retrieval from published notes; never mix topics or serve drafts."""
import json
import hashlib
import re
from pathlib import Path

from backend.numbers.bank import load_curriculum

NOTES_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "notes"


def get_topic_notes(topic, notes_dir=NOTES_DIR):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", topic):
        return ""
    # A sidecar is an explicit publication record, not an approval invented by code.
    path = Path(notes_dir) / f"{topic}.md"
    review = path.with_suffix(".review.json")
    if path.is_file() and review.is_file():
        try:
            metadata = json.loads(review.read_text(encoding="utf-8"))
            raw = path.read_bytes()
            if (metadata.get("status") == "approved" and metadata.get("reviewer")
                    and metadata.get("date")
                    and metadata.get("sha256") == hashlib.sha256(raw).hexdigest()):
                return raw.decode("utf-8").replace("\r\n", "\n").strip()
        except (OSError, ValueError, AttributeError):
            pass
    # Existing approved curriculum is the fallback knowledge base. No cross-topic search.
    curriculum = load_curriculum()
    if curriculum.get("status") == "approved":
        skill = next((s for s in curriculum["skills"] if s["id"] == topic), {})
        return str(skill.get("lesson", "")).strip()
    return ""

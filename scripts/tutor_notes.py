"""Inspect notes drafts or publish explicitly human-reviewed notes.

Publication is never run automatically. A named person must actually review the file.
"""
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from backend.numbers.bank import load_curriculum

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "reference" / "tutor-notes-v2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "publish"])
    parser.add_argument("topic", nargs="?")
    parser.add_argument("--reviewer")
    parser.add_argument("--review-date")
    parser.add_argument("--confirm-reviewed", action="store_true")
    args = parser.parse_args()
    known = {s["id"] for s in load_curriculum()["skills"]}
    if args.topic and (not re.fullmatch(r"[a-z0-9-]+", args.topic) or args.topic not in known):
        parser.error("Choose a topic in the current curriculum.")
    if args.action == "check":
        for topic in sorted(known if not args.topic else {args.topic}):
            path = DRAFTS / f"{topic}.md"
            if not path.exists():
                print(f"{topic}: missing draft")
                continue
            text = path.read_text(encoding="utf-8")
            print(f"{topic}: draft, {len(text.split())} words, ~{round(len(text)/4)} tokens (character estimate)")
        return
    if not (args.topic and args.reviewer and args.reviewer.strip()
            and args.review_date and args.confirm_reviewed):
        parser.error("Publication requires a topic, actual reviewer, review date and --confirm-reviewed.")
    reviewed = date.fromisoformat(args.review_date)
    if reviewed > date.today():
        parser.error("Review date cannot be in the future.")
    source = DRAFTS / f"{args.topic}.md"
    text = source.read_text(encoding="utf-8")
    # Publication is a separate copy. Draft sources retain their status and history.
    text = text.replace("Status: draft. Original material for human review.",
                        "Status: approved for tutoring after human review.")
    target = ROOT / "knowledge" / "notes" / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
    metadata = {"status": "approved", "reviewer": args.reviewer.strip(), "date": reviewed.isoformat(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    target.with_suffix(".review.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Published {args.topic}. Editing its file invalidates this review hash.")


if __name__ == "__main__":
    main()

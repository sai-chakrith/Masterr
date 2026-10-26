"""Validate, return to draft, or explicitly approve the Numbers curriculum.

Use `draft` before editing an approved curriculum. The content checksum makes
runtime loading fail closed if published content changes outside this workflow.

    python -m scripts.curriculum_review validate
    python -m scripts.curriculum_review draft
    # Edit content/numbers/curriculum.json, then:
    python -m scripts.curriculum_review validate
    python -m scripts.curriculum_review approve --reviewer 'Reviewer name' --date 2026-10-26
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from backend.curriculum import CURRICULUM_PATH, curriculum_digest, validate_curriculum


def mark_draft(document: dict) -> dict:
    result = deepcopy(document)
    result["status"] = "draft"
    result["schema_version"] = int(result.get("schema_version", 0)) + 1
    result.pop("review", None)
    result.pop("approval_checksum", None)
    problems = validate_curriculum(result)
    if problems:
        raise ValueError("Cannot return invalid curriculum to draft: " + "; ".join(problems))
    return result


def approve_document(document: dict, reviewer: str, review_date: str) -> dict:
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    try:
        if date.fromisoformat(review_date).isoformat() != review_date:
            raise ValueError
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    result = deepcopy(document)
    result["status"] = "approved"
    result["schema_version"] = int(result.get("schema_version", 0)) + 1
    result["review"] = {"reviewer": reviewer, "date": review_date}
    result["approval_checksum"] = curriculum_digest(result)
    problems = validate_curriculum(result)
    if problems:
        raise ValueError("Cannot approve curriculum: " + "; ".join(problems))
    return result


def save(document: dict, path: Path = CURRICULUM_PATH) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("draft")
    approve = sub.add_parser("approve")
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--date", required=True)
    args = parser.parse_args()
    document = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    try:
        if args.command == "validate":
            problems = validate_curriculum(document)
            print(json.dumps({"valid": not problems, "errors": problems}, indent=2))
            if problems:
                raise SystemExit(1)
            return
        if args.command == "draft":
            document = mark_draft(document)
            save(document)
            print(f"curriculum returned to draft at version {document['schema_version']}")
            return
        document = approve_document(document, args.reviewer, args.date)
        save(document)
        print(f"curriculum approved at version {document['schema_version']}")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

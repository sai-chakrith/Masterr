"""Review and publish exam-to-topic maps.

    python -m scripts.exam_profiles export data/exam_profiles.csv
    # Edit the CSV topic lists and bars, then:
    python -m scripts.exam_profiles apply-content data/exam_profiles.csv
    python -m scripts.exam_profiles validate
    python -m scripts.exam_profiles approve --reviewer 'Reviewer name' --date 2026-10-26

Content edits always return the catalog to draft. Approval requires a human
reviewer and ISO date and publishes every profile in the reviewed catalog.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from datetime import date
from pathlib import Path

from backend.exam_profiles import EXAM_PROFILES_PATH, validate_exam_profiles
from backend.curriculum import load_curriculum

COLUMNS = ("id", "name", "target_skill_ids", "default_mastery_bar", "topic_bars")
JSON_COLUMNS = {"target_skill_ids", "topic_bars"}


def export_profiles(path: Path, document: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for profile in document["profiles"]:
            writer.writerow({
                "id": profile["id"], "name": profile["name"],
                "target_skill_ids": json.dumps(profile["target_skill_ids"], ensure_ascii=False),
                "default_mastery_bar": profile.get("default_mastery_bar", 0.75),
                "topic_bars": json.dumps(profile.get("topic_bars", {}), ensure_ascii=False),
            })


def apply_profile_rows(document: dict, rows: list[dict]) -> dict:
    result = copy.deepcopy(document)
    profiles = []
    for row in rows:
        profile = {}
        for field in COLUMNS:
            raw = (row.get(field) or "").strip()
            if field in JSON_COLUMNS:
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{row.get('id', '<missing>')}: {field} must be valid JSON") from exc
            elif field == "default_mastery_bar":
                try:
                    value = float(raw or "0.75")
                except ValueError as exc:
                    raise ValueError(f"{row.get('id', '<missing>')}: default_mastery_bar must be numeric") from exc
            else:
                value = raw
            profile[field] = value
        profiles.append(profile)
    result["profiles"] = profiles
    result["schema_version"] = int(result.get("schema_version", 0)) + 1
    result["status"] = "draft"
    for profile in result["profiles"]:
        profile.pop("review", None)
    problems = validate_exam_profiles(result)
    if problems:
        raise ValueError("; ".join(problems))
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
    result = copy.deepcopy(document)
    for profile in result["profiles"]:
        profile["review"] = {"reviewer": reviewer, "date": review_date}
    result["status"] = "approved"
    result["schema_version"] = int(result.get("schema_version", 0)) + 1
    problems = validate_exam_profiles(result)
    if problems:
        raise ValueError("Cannot approve profile catalog: " + "; ".join(problems))
    return result


def save(document: dict, path: Path = EXAM_PROFILES_PATH) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export_parser = sub.add_parser("export", help="write the current catalog to a review CSV")
    export_parser.add_argument("csv", type=Path)
    apply_parser = sub.add_parser("apply-content", help="save edited CSV rows as draft profiles")
    apply_parser.add_argument("csv", type=Path)
    sub.add_parser("validate", help="validate current profile data")
    approve_parser = sub.add_parser("approve", help="publish every profile after human review")
    approve_parser.add_argument("--reviewer", required=True)
    approve_parser.add_argument("--date", required=True)
    args = parser.parse_args()

    document = json.loads(EXAM_PROFILES_PATH.read_text(encoding="utf-8"))
    try:
        if args.command == "export":
            export_profiles(args.csv, document)
            print(f"wrote {args.csv}")
            return
        if args.command == "apply-content":
            with args.csv.open(newline="", encoding="utf-8") as stream:
                document = apply_profile_rows(document, list(csv.DictReader(stream)))
            save(document)
            print(f"saved {len(document['profiles'])} draft profiles at version {document['schema_version']}")
            return
        if args.command == "validate":
            problems = validate_exam_profiles(document)
            print(json.dumps({"valid": not problems, "errors": problems}, indent=2))
            if problems:
                raise SystemExit(1)
            return
        if args.command == "approve":
            document = approve_document(document, args.reviewer, args.date)
            save(document)
            print(f"approved {len(document['profiles'])} exam profiles at version {document['schema_version']}")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

"""Human review workflow for draft misconception explanations and distractor tags.

    python -m scripts.misconception_review validate
    python -m scripts.misconception_review export review.csv
    python -m scripts.misconception_review apply-content review.csv
    python -m scripts.misconception_review apply-review review.csv

An approved assessment item may only reference misconceptions that also have an
explicit human review record. Editing an explanation returns it to draft.
"""
import argparse
import copy
import csv
import json
from datetime import date
from pathlib import Path

from backend.numbers.bank import CONTENT, load_questions, validate_bank

PATH = CONTENT / "misconceptions.json"
COLUMNS = ("id", "skill_id", "description", "short_fix", "review_status",
           "reviewer", "review_date")


def load_document():
    return json.loads(PATH.read_text(encoding="utf-8"))


def validate_document(document):
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int:
        return ["document requires an integer schema_version"]
    if not isinstance(document.get("misconceptions"), list):
        return ["misconceptions must be a list"]
    return validate_bank(load_questions(), document["misconceptions"])


def save_document(document):
    errors = validate_document(document)
    if errors:
        raise ValueError("Refusing to save invalid misconception content: " + "; ".join(errors))
    PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_csv(path):
    document = load_document()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for item in document["misconceptions"]:
            review = item.get("review") or {}
            writer.writerow({**{key: item.get(key, "") for key in COLUMNS[:5]},
                             "reviewer": review.get("reviewer", ""),
                             "review_date": review.get("date", "")})


def apply_content_rows(document, rows):
    working = copy.deepcopy(document)
    index = {item["id"]: item for item in working["misconceptions"]}
    changed = []
    for row in rows:
        item_id = row.get("id", "").strip()
        item = index.get(item_id)
        if item is None:
            raise ValueError(f"Unknown misconception id: {item_id}")
        if row.get("skill_id", "").strip() != item["skill_id"]:
            raise ValueError(f"{item_id}: skill_id is immutable")
        updates = {key: row.get(key, "").strip() for key in ("description", "short_fix")}
        if any(not value for value in updates.values()):
            raise ValueError(f"{item_id}: description and short_fix are required")
        if any(item.get(key) != value for key, value in updates.items()):
            item.update(updates)
            item["review_status"] = "draft"
            item.pop("review", None)
            changed.append(item_id)
    working["schema_version"] = document["schema_version"] + bool(changed)
    if changed:
        save_document(working)
    return changed


def apply_review_rows(document, rows):
    working = copy.deepcopy(document)
    index = {item["id"]: item for item in working["misconceptions"]}
    changed = []
    for row in rows:
        item_id = row.get("id", "").strip()
        item = index.get(item_id)
        if item is None:
            raise ValueError(f"Unknown misconception id: {item_id}")
        status = row.get("review_status", "").strip()
        if status not in {"draft", "approved"}:
            raise ValueError(f"{item_id}: review_status must be draft or approved")
        review = None
        if status == "approved":
            reviewer, review_date = row.get("reviewer", "").strip(), row.get("review_date", "").strip()
            if not reviewer:
                raise ValueError(f"{item_id}: reviewer is required for approval")
            try:
                if date.fromisoformat(review_date).isoformat() != review_date:
                    raise ValueError
            except ValueError as exc:
                raise ValueError(f"{item_id}: review_date must use YYYY-MM-DD") from exc
            review = {"reviewer": reviewer, "date": review_date}
        if item.get("review_status", "draft") == status and item.get("review") == review:
            continue
        item["review_status"] = status
        if review is None:
            item.pop("review", None)
        else:
            item["review"] = review
        changed.append(item_id)
    working["schema_version"] = document["schema_version"] + bool(changed)
    if changed:
        save_document(working)
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review misconception copy and distractor mappings")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    export = sub.add_parser("export")
    export.add_argument("csv", type=Path)
    for command in ("apply-content", "apply-review"):
        subparser = sub.add_parser(command)
        subparser.add_argument("csv", type=Path)
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_document(load_document())
        if errors:
            parser.exit(1, "\n".join(errors) + "\n")
        data = load_document()
        approved = sum(item.get("review_status") == "approved" for item in data["misconceptions"])
        print(json.dumps({"valid": True, "total": len(data["misconceptions"]), "approved": approved}, indent=2))
        return 0
    if args.command == "export":
        export_csv(args.csv)
        print("wrote", args.csv)
        return 0
    document = load_document()
    with args.csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    try:
        changed = (apply_content_rows(document, rows) if args.command == "apply-content"
                   else apply_review_rows(document, rows))
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"Updated {len(changed)} misconception records: {', '.join(changed) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

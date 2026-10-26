"""C2 question-bank tooling: coverage audit, tag-review sheet, validation forms, tag flags.

    python -m scripts.question_bank audit
    python -m scripts.question_bank export data/question_bank.csv
    python -m scripts.question_bank apply-tags data/question_bank.csv
    python -m scripts.question_bank assign-forms
    python -m scripts.question_bank flag --database-url sqlite:///./data/local.db

The tag review is done by people in the CSV (difficulty_level, hidden, sub_topic); this
tool only moves those columns back into content/numbers/questions.json. A changed tag
creates a new question version, because imported versions are immutable.
"""
import argparse
import copy
import csv
import json
import sys
from datetime import date
from pathlib import Path

from backend.numbers.bank import CONTENT, load_curriculum, validate_bank
from backend.numbers.coverage import audit, flag_tags, split_forms

QUESTIONS = CONTENT / "questions.json"
COLUMNS = ("id", "skill_id", "family_id", "purpose", "difficulty", "difficulty_level", "hidden",
           "validation_form", "sub_topic", "review_status", "prompt", "answer", "solution", "hints",
           "validator", "reasoning_rubric", "possible_misconception", "follow_up", "options", "provenance",
           "template_id", "generation", "tag_review", "reviewer", "review_date", "review_note")
TAGS = ("difficulty_level", "hidden", "sub_topic")
CONTENT_FIELDS = ("prompt", "answer", "solution", "hints", "validator", "reasoning_rubric",
                  "possible_misconception", "follow_up", "difficulty", "options")
JSON_FIELDS = {"hints", "validator", "reasoning_rubric", "options"}


def load():
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def save(document):
    errors = validate_bank(document["questions"])
    if errors:
        raise SystemExit("Refusing to save an invalid bank:\n" + "\n".join(errors))
    QUESTIONS.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_audit(_):
    skills = [s["id"] for s in load_curriculum()["skills"]]
    reports = audit(load()["questions"], skills)
    print(json.dumps(reports, indent=2))
    return 1 if any(r["problems"] for r in reports.values()) else 0


def cmd_export(args):
    with open(args.csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, COLUMNS)
        writer.writeheader()
        for q in load()["questions"]:
            row = {c: q.get(c, "") if q.get(c) is not None else "" for c in COLUMNS}
            for column in ("hints", "validator", "reasoning_rubric", "options", "generation"):
                if isinstance(row[column], (dict, list)):
                    row[column] = json.dumps(row[column], ensure_ascii=False)
            review = q.get("review") or {}
            row.update(reviewer=review.get("reviewer", ""), review_date=review.get("date", ""),
                       review_note=review.get("note", ""))
            writer.writerow(row)
    print("wrote", args.csv)
    return 0


def parse_tag(column, text):
    text = text.strip()
    if column == "difficulty_level":
        return int(text) if text else None
    if column == "hidden":
        if text.lower() not in ("true", "false", ""):
            raise ValueError(f"hidden must be true or false, got {text!r}")
        return text.lower() == "true"
    return text or None


def cmd_apply_tags(args):
    document = load()
    by_id = {q["id"]: q for q in document["questions"]}
    changed = []
    with open(args.csv, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            q = by_id.get(row["id"])
            if q is None:
                raise SystemExit(f"Unknown question id in sheet: {row['id']}")
            updates = {c: parse_tag(c, row.get(c, "")) for c in TAGS}
            if all(q.get(c) == updates[c] or (q.get(c) in (None, False) and updates[c] in (None, False))
                   for c in TAGS):
                continue
            for column, value in updates.items():
                if value is None or (column == "hidden" and value is False):
                    q.pop(column, None)
                else:
                    q[column] = value
            if not q.get("hidden"):
                q.pop("validation_form", None)
            q["version"] = q.get("version", 1) + 1
            if q["review_status"] == "approved":
                q["review_status"] = "draft"  # a retagged question needs a fresh human sign-off
                q.pop("review", None)
            changed.append(q["id"])
    save(document)
    print(f"Updated {len(changed)} questions (new versions): {', '.join(changed) or 'none'}")
    if changed:
        print("Run assign-forms if hidden flags changed, then re-review and import.")
    return 0


def parse_content_value(column, text, qid):
    text = text.strip()
    if column == "answer":
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"{qid}: answer must be an integer") from exc
    if column in JSON_FIELDS:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{qid}: {column} must contain valid JSON") from exc
    return text


def apply_content_rows(document, rows):
    """Apply editor changes as new draft versions; edits always revoke approval."""
    working = copy.deepcopy(document)
    by_id = {q["id"]: q for q in working["questions"]}
    changed = []
    for row in rows:
        qid = row.get("id", "").strip()
        q = by_id.get(qid)
        if q is None:
            raise ValueError(f"Unknown question id in content sheet: {qid}")
        updates = {}
        removals = set()
        for column in CONTENT_FIELDS:
            if column not in row:
                continue
            raw = row.get(column, "")
            if not str(raw).strip() and column in {"reasoning_rubric", "possible_misconception",
                                                    "follow_up", "difficulty"}:
                if q.get(column) not in (None, "", [], {}):
                    removals.add(column)
                continue
            value = parse_content_value(column, raw, qid)
            if value != q.get(column):
                updates[column] = value
        if not updates and not removals:
            continue
        q.update(updates)
        for column in removals:
            q.pop(column, None)
        q["version"] = q.get("version", 1) + 1
        q["review_status"] = "draft"
        q.pop("review", None)
        changed.append(qid)
    errors = validate_bank(working["questions"])
    if errors:
        raise ValueError("Content edits produced an invalid bank: " + "; ".join(errors))
    document["questions"] = working["questions"]
    return changed


def cmd_apply_content(args):
    document = load()
    with open(args.csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    try:
        changed = apply_content_rows(document, rows)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    save(document)
    print(f"Updated {len(changed)} content items as draft versions: {', '.join(changed) or 'none'}")
    print("Content edits revoke approval. Re-review each changed version before publication.")
    return 0


def apply_review_rows(document, rows):
    """Apply explicit human review decisions; never infer or fabricate approval."""
    working = copy.deepcopy(document)
    by_id = {q["id"]: q for q in working["questions"]}
    changed = []
    for row in rows:
        qid = row.get("id", "").strip()
        q = by_id.get(qid)
        if q is None:
            raise ValueError(f"Unknown question id in review sheet: {qid}")
        status = row.get("review_status", "").strip()
        if status not in {"draft", "approved", "withdrawn"}:
            raise ValueError(f"{qid}: review_status must be draft, approved or withdrawn")
        review = None
        if status in {"approved", "withdrawn"}:
            reviewer = row.get("reviewer", "").strip()
            review_date = row.get("review_date", "").strip()
            note = row.get("review_note", "").strip()
            if not reviewer:
                raise ValueError(f"{qid}: reviewer is required for approval or withdrawal")
            try:
                if date.fromisoformat(review_date).isoformat() != review_date:
                    raise ValueError
            except ValueError as exc:
                raise ValueError(f"{qid}: review_date must be YYYY-MM-DD") from exc
            review = {"reviewer": reviewer, "date": review_date}
            if note:
                review["note"] = note
        if q.get("review_status") == status and q.get("review") == review:
            continue
        q["version"] = q.get("version", 1) + 1
        q["review_status"] = status
        if review is None:
            q.pop("review", None)
        else:
            q["review"] = review
        changed.append(qid)
    errors = validate_bank(working["questions"])
    if errors:
        raise ValueError("Review sheet produced an invalid bank: " + "; ".join(errors))
    document["questions"] = working["questions"]
    return changed


def cmd_apply_review(args):
    document = load()
    with open(args.csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    try:
        changed = apply_review_rows(document, rows)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    save(document)
    print(f"Updated {len(changed)} review decisions (new versions): {', '.join(changed) or 'none'}")
    print("Review decisions are metadata only; check question correctness, wording, solutions and tags before approval.")
    return 0


def cmd_assign_forms(_):
    document = load()
    skills = {q["skill_id"] for q in document["questions"]}
    changed = 0
    for skill in sorted(skills):
        hidden = [q for q in document["questions"] if q["skill_id"] == skill and q.get("hidden")
                  and q.get("difficulty_level")]
        for q in document["questions"]:
            if q["skill_id"] == skill and q.get("hidden") and q.get("difficulty_level"):
                form = split_forms(hidden)[q["id"]]
                if q.get("validation_form") != form:
                    q["validation_form"] = form
                    q["version"] = q.get("version", 1) + 1
                    changed += 1
    save(document)
    print(f"Assigned validation forms; {changed} questions changed")
    return 0


def cmd_flag(args):
    from sqlalchemy import select

    from backend.db import make_engine, transaction
    from backend.models import Assignment, Attempt, Question

    engine = make_engine(args.database_url)
    with transaction(engine) as db:
        rows = db.execute(select(Question.id, Question.difficulty_level, Attempt.predicted_probability,
                                 Attempt.correct).join(Assignment, Assignment.question_id == Question.id)
                          .join(Attempt, Attempt.assignment_id == Assignment.id)
                          .where(Attempt.scoring_version == "new", Attempt.assistance == "independent")).all()
    flags = flag_tags(rows)
    print(json.dumps(flags, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mastrr question-bank tooling (C2)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit").set_defaults(run=cmd_audit)
    p = sub.add_parser("export")
    p.add_argument("csv", type=Path)
    p.set_defaults(run=cmd_export)
    p = sub.add_parser("apply-tags")
    p.add_argument("csv", type=Path)
    p.set_defaults(run=cmd_apply_tags)
    p = sub.add_parser("apply-review")
    p.add_argument("csv", type=Path)
    p.set_defaults(run=cmd_apply_review)
    p = sub.add_parser("apply-content")
    p.add_argument("csv", type=Path)
    p.set_defaults(run=cmd_apply_content)
    sub.add_parser("assign-forms").set_defaults(run=cmd_assign_forms)
    p = sub.add_parser("flag")
    p.add_argument("--database-url", default="sqlite:///./data/local.db")
    p.set_defaults(run=cmd_flag)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

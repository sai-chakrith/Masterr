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
import csv
import json
import sys
from pathlib import Path

from backend.numbers.bank import CONTENT, load_curriculum, validate_bank
from backend.numbers.coverage import audit, flag_tags, split_forms

QUESTIONS = CONTENT / "questions.json"
COLUMNS = ("id", "skill_id", "family_id", "purpose", "difficulty", "difficulty_level", "hidden",
           "validation_form", "sub_topic", "review_status", "prompt", "answer")
TAGS = ("difficulty_level", "hidden", "sub_topic")


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
            writer.writerow({c: q.get(c, "") if q.get(c) is not None else "" for c in COLUMNS})
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
    sub.add_parser("assign-forms").set_defaults(run=cmd_assign_forms)
    p = sub.add_parser("flag")
    p.add_argument("--database-url", default="sqlite:///./data/local.db")
    p.set_defaults(run=cmd_flag)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

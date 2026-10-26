"""Attach deterministic, tagged draft multiple-choice options to pilot arithmetic questions.

Every changed item remains in draft and receives a new question version. Review
the option's numerical plausibility and misconception tag before question approval.

    python -m scripts.add_distractors
"""
import json

from backend.numbers.bank import CONTENT, load_misconceptions, validate_bank
from backend.numbers.distractors import PILOT_SKILLS, make_options

PATH = CONTENT / "questions.json"


def attach_options(document):
    working = json.loads(json.dumps(document))
    changed = []
    for question in working["questions"]:
        if question.get("skill_id") not in PILOT_SKILLS or question.get("options"):
            continue
        question["options"] = make_options(question)
        question["version"] = question.get("version", 1) + 1
        question["review_status"] = "draft"
        question.pop("review", None)
        changed.append(question["id"])
    errors = validate_bank(working["questions"], load_misconceptions())
    if errors:
        raise ValueError("Draft distractors failed bank validation: " + "; ".join(errors))
    return working, changed


def main():
    document = json.loads(PATH.read_text(encoding="utf-8"))
    try:
        updated, changed = attach_options(document)
    except (KeyError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if changed:
        PATH.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Attached draft distractors to {len(changed)} questions; none were approved.")


if __name__ == "__main__":
    main()

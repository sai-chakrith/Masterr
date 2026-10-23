"""Run with python -m backend.numbers to inspect validation and coverage."""

import json
from collections import Counter

from .bank import load_curriculum, load_questions, validate_bank


def main():
    curriculum, questions = load_curriculum(), load_questions()
    errors = validate_bank(questions)
    print(json.dumps({
        "module": curriculum["title"],
        "skills": len(curriculum["skills"]),
        "questions": len(questions),
        "review_status": dict(Counter(q["review_status"] for q in questions)),
        "approved_questions_available": sum(q["review_status"] == "approved" for q in questions),
        "validation_errors": errors,
        "note": "Arithmetic checks do not establish content approval or learning effectiveness."
    }, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()

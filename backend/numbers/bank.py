"""Private question bank. Never send an entire bank record to a student client.

This module deliberately has no LLM dependency. Arithmetic is checked independently
of prose, which must still receive human review before publication.
"""

import json
from math import gcd, isqrt, lcm
from pathlib import Path


CONTENT = Path(__file__).resolve().parents[2] / "content" / "numbers"


def load_curriculum():
    return json.loads((CONTENT / "curriculum.json").read_text(encoding="utf-8"))


def load_questions():
    return json.loads((CONTENT / "questions.json").read_text(encoding="utf-8"))["questions"]


def compute_answer(spec):
    """Evaluate allowlisted arithmetic; never execute model-produced code."""
    kind = spec["kind"]
    if kind == "even_count":
        low, high = spec["low"], spec["high"]
        if low > high:
            raise ValueError("Invalid integer interval")
        return high // 2 - (low - 1) // 2
    if kind == "prime_count":
        values = spec["values"]
        return sum(n > 1 and all(n % d for d in range(2, isqrt(n) + 1)) for n in values)
    if kind == "factor_count":
        n = spec["number"]
        if n < 1:
            raise ValueError("Positive factors require a positive integer")
        return sum(1 if d * d == n else 2 for d in range(1, isqrt(n) + 1) if n % d == 0)
    if kind == "missing_digit":
        pattern, divisor = spec["pattern"], spec["divisor"]
        if pattern.count("?") != 1 or divisor < 1:
            raise ValueError("Need one missing digit and a positive divisor")
        candidates = [d for d in range(10) if not (pattern.startswith("?") and d == 0)
                      and int(pattern.replace("?", str(d))) % divisor == 0]
        if len(candidates) != 1:
            raise ValueError("Missing-digit question must have exactly one answer")
        return candidates[0]
    if kind in {"gcd", "lcm"}:
        a, b = spec["a"], spec["b"]
        if min(a, b) < 1:
            raise ValueError("HCF/LCM questions require positive integers")
        return gcd(a, b) if kind == "gcd" else lcm(a, b)
    if kind == "remainder":
        if spec["divisor"] < 1:
            raise ValueError("Divisor must be positive")
        return spec["number"] % spec["divisor"]
    if kind == "power_remainder":
        if spec["exponent"] < 0 or spec["divisor"] < 1:
            raise ValueError("Need a nonnegative exponent and positive divisor")
        return pow(spec["base"], spec["exponent"], spec["divisor"])
    raise ValueError(f"Unsupported validator: {kind}")


def validate_bank(questions=None):
    """Return errors, without promoting drafts to approved content."""
    questions = load_questions() if questions is None else questions
    skills = {s["id"] for s in load_curriculum()["skills"]}
    errors, seen = [], set()
    for question in questions:
        qid = question.get("id", "<missing>")
        try:
            if qid in seen:
                raise ValueError("Duplicate question id")
            seen.add(qid)
            if question["skill_id"] not in skills:
                raise ValueError("Unknown skill")
            for key in ("family_id", "prompt", "solution", "hints", "provenance"):
                if not question[key]:
                    raise ValueError(f"Missing {key}")
            if question["review_status"] not in {"draft", "approved", "withdrawn"}:
                raise ValueError("Unknown review status")
            if question["review_status"] == "approved" and not question.get("review"):
                raise ValueError("Approval requires a human review record")
            if question["purpose"] not in {"diagnostic", "practice", "verification", "review"}:
                raise ValueError("Unknown purpose")
            if type(question["answer"]) is not int:
                raise ValueError("Expected an integer answer")
            if compute_answer(question["validator"]) != question["answer"]:
                raise ValueError("Stored answer disagrees with arithmetic validator")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{qid}: {exc}")
    return errors


def select_question(skill_id, purpose, exposed_families=()):
    """Only reviewed content is eligible; never silently recycle a family."""
    if validate_bank():
        raise ValueError("Bank validation failed")
    for question in load_questions():
        if (question["review_status"] == "approved"
                and question["skill_id"] == skill_id
                and question["purpose"] == purpose
                and question["family_id"] not in exposed_families):
            return question
    return None  # Caller must report insufficient coverage.


def student_view(question):
    """Explicit allowlist excludes answers, solutions, hints, and validators."""
    return {key: question[key] for key in ("id", "skill_id", "prompt", "difficulty")}

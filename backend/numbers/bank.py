"""Private question bank. Never send an entire bank record to a student client.

This module deliberately has no LLM dependency. Arithmetic is checked independently
of prose, which must still receive human review before publication.
"""

import ast
import json
from datetime import date
from math import gcd, isqrt, lcm
from pathlib import Path


CONTENT = Path(__file__).resolve().parents[2] / "content" / "numbers"
MISCONCEPTIONS = CONTENT / "misconceptions.json"


def load_curriculum():
    return json.loads((CONTENT / "curriculum.json").read_text(encoding="utf-8"))


def load_questions():
    return json.loads((CONTENT / "questions.json").read_text(encoding="utf-8"))["questions"]


def load_misconceptions():
    if not MISCONCEPTIONS.exists():
        return []
    return json.loads(MISCONCEPTIONS.read_text(encoding="utf-8")).get("misconceptions", [])


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
    if kind == "expression":
        return evaluate(spec["expr"])
    raise ValueError(f"Unsupported validator: {kind}")


def _is_prime(n):
    return n > 1 and all(n % d for d in range(2, isqrt(n) + 1))


def _bounded_range(low, high):
    if high - low > 100000:
        raise ValueError("Range too large")
    return range(low, high + 1)


def _factor_count(n):
    return compute_answer({"kind": "factor_count", "number": n})


def _factors(n):
    if n < 1 or n > 10**9:
        raise ValueError("Factors need a positive integer up to 10^9")
    return [d for d in range(1, isqrt(n) + 1) if n % d == 0] + [n // d for d in range(isqrt(n), 0, -1)
                                                                 if n % d == 0 and d * d != n]


# Allowlisted helpers for "expression" validators. Each is plain integer arithmetic.
HELPERS = {
    "gcd": gcd, "lcm": lcm, "abs": abs, "min": min, "max": max,
    "is_prime": lambda n: int(_is_prime(n)),
    "factor_count": _factor_count,
    "factor_sum": lambda n: sum(_factors(n)),
    "odd_factor_count": lambda n: sum(d % 2 for d in _factors(n)),
    "even_factor_count": lambda n: sum(d % 2 == 0 for d in _factors(n)),
    "prime_factor_count": lambda n: sum(_is_prime(d) for d in _factors(n)),
    "largest_prime_factor": lambda n: max(d for d in _factors(n) if _is_prime(d)),
    "prime_count": lambda low, high: sum(_is_prime(n) for n in _bounded_range(low, high)),
    "multiples": lambda low, high, d: sum(n % d == 0 for n in _bounded_range(low, high)),
    "digit_sum": lambda n: sum(int(c) for c in str(abs(n))),
    "digit_count": lambda n: len(str(abs(n))),
    "trailing_zeros_factorial": lambda n: sum(n // 5**k for k in range(1, 30)),
    "coprime_count": lambda low, high, n: sum(gcd(k, n) == 1 for k in _bounded_range(low, high)),
    "isqrt": isqrt,
    "smallest_prime_factor": lambda n: min(d for d in _factors(n) if _is_prime(d)),
    "prime_factor_sum": lambda n: sum(d for d in _factors(n) if _is_prime(d)),
    "square_factor_count": lambda n: sum(isqrt(d) ** 2 == d for d in _factors(n)),
    "prime_sum": lambda low, high: sum(n for n in _bounded_range(low, high) if _is_prime(n)),
    "count_with_factor_count": lambda low, high, k: sum(_factor_count(n) == k for n in _bounded_range(max(low, 1), high)),
    "smallest_with_factor_count": lambda k: next(n for n in range(1, 100001) if _factor_count(n) == k),
    "count_divisible": lambda d, *values: sum(v % d == 0 for v in values),
    "smallest_n_linear": lambda a, b, d: next(n for n in range(1, d + 1) if (a * n + b) % d == 0),
    "smallest_with_remainders": lambda *pairs: next(
        n for n in range(1, 100001) if all(n % pairs[i] == pairs[i + 1] for i in range(0, len(pairs), 2))),
}
_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant,
          ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd)


def evaluate(expr):
    """Integer calculator for answer keys: literals, + - * // % **, and HELPERS. No other names."""
    if not isinstance(expr, str) or len(expr) > 300:
        raise ValueError("Expression must be short text")
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _NODES):
            raise ValueError(f"Disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Constant) and type(node.value) is not int:
            raise ValueError("Only integer literals are allowed")
        if isinstance(node, ast.Name) and node.id not in HELPERS:
            raise ValueError(f"Unknown helper: {node.id}")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.keywords):
            raise ValueError("Only plain helper calls are allowed")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            if not isinstance(node.right, ast.Constant) or node.right.value > 64:
                raise ValueError("Exponents must be literal and at most 64")

    def run(node):
        if isinstance(node, ast.Expression):
            return run(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            value = run(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a, b = run(node.left), run(node.right)
            op = type(node.op)
            if op in (ast.FloorDiv, ast.Mod) and b == 0:
                raise ValueError("Division by zero")
            return {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
                    ast.FloorDiv: lambda: a // b, ast.Mod: lambda: a % b, ast.Pow: lambda: a ** b}[op]()
        if isinstance(node, ast.Call):
            return HELPERS[node.func.id](*[run(arg) for arg in node.args])
        raise ValueError("Unsupported expression")

    value = run(tree)
    if type(value) is not int:
        raise ValueError("Expression must produce an integer")
    return value


def validate_bank(questions=None, misconceptions=None):
    """Return errors, without promoting drafts to approved content."""
    questions = load_questions() if questions is None else questions
    misconceptions = load_misconceptions() if misconceptions is None else misconceptions
    skills = {s["id"] for s in load_curriculum()["skills"]}
    errors, seen, misconception_index = [], set(), {}
    for misconception in misconceptions:
        mid = misconception.get("id")
        if not isinstance(mid, str) or not mid or mid in misconception_index:
            errors.append(f"misconception {mid!r}: IDs must be present and unique")
            continue
        if misconception.get("skill_id") not in skills:
            errors.append(f"{mid}: unknown skill")
        if not all(isinstance(misconception.get(field), str) and misconception[field].strip()
                   for field in ("description", "short_fix")):
            errors.append(f"{mid}: description and short_fix are required")
        review_status = misconception.get("review_status", "draft")
        if review_status not in {"draft", "approved"}:
            errors.append(f"{mid}: review_status must be draft or approved")
        if review_status == "approved":
            review = misconception.get("review")
            if not isinstance(review, dict) or not all(
                isinstance(review.get(key), str) and review[key].strip()
                for key in ("reviewer", "date")
            ):
                errors.append(f"{mid}: approval requires a human reviewer and date")
            else:
                try:
                    if date.fromisoformat(review["date"]).isoformat() != review["date"]:
                        raise ValueError
                except ValueError:
                    errors.append(f"{mid}: review date must use YYYY-MM-DD")
        misconception_index[mid] = misconception
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
            options = question.get("options")
            if options is not None:
                if not isinstance(options, list) or len(options) != 4:
                    raise ValueError("Multiple-choice items need exactly four options")
                ids, values = set(), set()
                correct_values = []
                for option in options:
                    if not isinstance(option, dict):
                        raise ValueError("Every option must be an object")
                    option_id, text, value = option.get("id"), option.get("text"), option.get("value")
                    if not isinstance(option_id, str) or not option_id or option_id in ids:
                        raise ValueError("Option IDs must be non-empty and unique")
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError("Every option needs display text")
                    if type(value) is not int or value in values:
                        raise ValueError("Option values must be distinct integers")
                    ids.add(option_id)
                    values.add(value)
                    if value == question["answer"]:
                        correct_values.append(option)
                    else:
                        mid = option.get("misconception_id")
                        if mid not in misconception_index:
                            raise ValueError(f"Wrong option {option_id} needs a known misconception tag")
                        if misconception_index[mid].get("skill_id") != question["skill_id"]:
                            raise ValueError(f"Wrong option {option_id} has a misconception from another skill")
                        if (question["review_status"] == "approved"
                                and misconception_index[mid].get("review_status", "draft") != "approved"):
                            raise ValueError(f"Wrong option {option_id} uses an unreviewed misconception")
                if len(correct_values) != 1 or correct_values[0].get("misconception_id"):
                    raise ValueError("Exactly one correct option is required and it cannot carry a misconception")
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

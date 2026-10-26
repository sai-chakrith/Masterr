"""Generate deterministic, validated arithmetic practice or assessment drafts.

Generated items are always drafts. Run the question-bank review workflow before
they can be served to learners. `--assessment` generates the weighted 35-item
assessment pool, including hidden Form A/B candidates, for each selected skill.
The templates cover arithmetic skills in the current Numbers curriculum; they
are not replacements for human review or exam-specific content validation.

    python -m scripts.generate_questions --count 40 --seed 20261026
    python -m scripts.generate_questions --assessment --seed 20261026 --skills percentages profit-loss
"""
from __future__ import annotations

import argparse
import json
import random
import re
from math import gcd

from backend.numbers.bank import CONTENT, compute_answer, load_curriculum, validate_bank
from backend.numbers.coverage import HIDDEN_SPLIT, TARGET_SPLIT, audit, split_forms

QUESTIONS = CONTENT / "questions.json"


def _candidate(skill_id: str, serial: int, rng: random.Random, level: int | None = None) -> dict:
    level = level or (serial - 1) % 5 + 1
    if skill_id == "integer-properties":
        low = rng.randrange(1, 80, 2) if level < 4 else rng.randrange(-30, 50, 2) + 1
        high = low + rng.randrange(8, 36, 2)
        validator = {"kind": "even_count", "low": low, "high": high}
        prompt = f"How many even integers are there from {low} to {high}, inclusive?"
        solution = f"The even integers in the interval number {compute_answer(validator)}."
        template = "even-count-inclusive-v1"
        hints = ["List the first and last even integers in the interval.",
                 "Count the even terms in the arithmetic sequence, including both ends."]
    elif skill_id == "divisibility":
        valid = [(divisor, f"{a}{b}?")
                 for divisor in (3, 6, 9) for a in range(1, 10) for b in range(10)
                 if len([d for d in range(10) if int(f"{a}{b}{d}") % divisor == 0]) == 1]
        if not valid:
            raise ValueError("Could not generate a unique missing-digit item")
        divisor, pattern = rng.choice(valid)
        validator = {"kind": "missing_digit", "pattern": pattern, "divisor": divisor}
        prompt = f"What digit replaces ? in {pattern} so the number is divisible by {divisor}?"
        solution = f"Testing the divisibility rule gives the unique digit {compute_answer(validator)}."
        template = "unique-missing-digit-v1"
        hints = ["Use the divisibility rule for the stated divisor.",
                 "Test each possible digit and keep the one that satisfies the rule."]
    elif skill_id == "primes-factors":
        n = rng.randrange(12, 181 if level > 2 else 61)
        validator = {"kind": "factor_count", "number": n}
        prompt = f"How many positive factors does {n} have?"
        solution = f"Pair factors of {n}; a square-root factor is counted once. There are {compute_answer(validator)}."
        template = "positive-factor-count-v1"
        hints = ["List factor pairs, stopping when the smaller factor passes the square root.",
                 "Count each factor pair once; count a repeated square-root factor only once."]
    elif skill_id == "hcf-lcm":
        a, b = rng.sample(range(4, 61 if level > 2 else 31), 2)
        kind = rng.choice(("gcd", "lcm"))
        validator = {"kind": kind, "a": a, "b": b}
        label = "greatest common factor" if kind == "gcd" else "least common multiple"
        prompt = f"Find the {label} of {a} and {b}."
        solution = f"The {label} of {a} and {b} is {compute_answer(validator)}."
        template = f"{kind}-pair-v1"
        hints = ["Write the prime factorisation of each number.",
                 "For the greatest common factor use shared minimum powers; for the least common multiple use maximum powers."]
    elif skill_id == "remainders":
        kind = rng.choice(("remainder", "power_remainder"))
        if kind == "remainder":
            number = rng.randrange(100, 10000 if level > 2 else 1000)
            divisor = rng.randrange(3, 31)
            validator = {"kind": kind, "number": number, "divisor": divisor}
            prompt = f"What is the remainder when {number} is divided by {divisor}?"
            solution = f"Write {number} as a multiple of {divisor} plus its remainder: {compute_answer(validator)}."
        else:
            base, exponent, divisor = rng.randrange(2, 13), rng.randrange(3, 21), rng.randrange(3, 13)
            validator = {"kind": kind, "base": base, "exponent": exponent, "divisor": divisor}
            prompt = f"What is the remainder when {base}^{exponent} is divided by {divisor}?"
            solution = f"Reduce powers modulo {divisor}; the remainder is {compute_answer(validator)}."
        template = f"{kind}-practice-v1"
        hints = ["Reduce the number or powers modulo the divisor.",
                 "Use quotient-remainder form and check that the result is smaller than the divisor."]
    elif skill_id == "digits-cyclicity":
        base, exponent = rng.randrange(2, 10), rng.randrange(3, 31)
        validator = {"kind": "power_remainder", "base": base, "exponent": exponent, "divisor": 10}
        prompt = f"What is the units digit of {base}^{exponent}?"
        solution = f"The power's remainder modulo 10 is its units digit: {compute_answer(validator)}."
        template = "units-digit-cycle-v1"
        hints = ["Write the units digits of the first few powers and find the repeating cycle.",
                 "Reduce the exponent by the cycle length, then read the matching position."]
    elif skill_id == "percentages":
        amount = rng.randrange(2, 61) * 100
        rate = rng.choice((5, 10, 12, 15, 20, 25, 30, 40))
        validator = {"kind": "expression", "expr": f"{amount}*{rate}//100"}
        prompt = f"What is {rate}% of {amount}?"
        solution = f"Convert {rate}% to a fraction out of 100 and multiply: {compute_answer(validator)}."
        template = "percentage-of-amount-v1"
        hints = ["Write the percentage as a fraction out of 100.", "Multiply the amount by the percentage, then divide by 100."]
    elif skill_id == "profit-loss":
        cost = rng.randrange(2, 61) * 100
        rate = rng.choice((5, 10, 15, 20, 25))
        is_profit = rng.choice((True, False))
        operation = "+" if is_profit else "-"
        validator = {"kind": "expression", "expr": f"{cost}{operation}{cost}*{rate}//100"}
        prompt = f"An item costs {cost}. Find its selling price at a {rate}% {'profit' if is_profit else 'loss'}."
        solution = f"The {'profit' if is_profit else 'loss'} is {rate}% of cost; selling price = {compute_answer(validator)}."
        template = "profit-loss-selling-price-v1"
        hints = ["Calculate profit or loss as a percentage of the cost price.", "Add profit to cost or subtract loss from cost."]
    elif skill_id == "simple-interest":
        principal = rng.randrange(2, 31) * 500
        rate = rng.choice((4, 5, 8, 10, 12))
        years = rng.randrange(1, 6)
        validator = {"kind": "expression", "expr": f"{principal}*{rate}*{years}//100"}
        prompt = f"Find the simple interest on {principal} at {rate}% per year for {years} years."
        solution = f"Use principal × rate × time / 100: the interest is {compute_answer(validator)}."
        template = "simple-interest-v1"
        hints = ["Simple interest uses the original principal each year.", "Substitute principal, annual rate and years into PRT/100."]
    elif skill_id == "compound-interest":
        rate = rng.choice((5, 10, 20, 25, 50))
        years = rng.randrange(1, 4)
        principal = (100 ** years) * rng.randrange(1, 1000)
        factor = 100 + rate
        validator = {"kind": "expression", "expr": f"{principal}*{factor ** years}//{100 ** years}-{principal}"}
        prompt = f"Find the compound interest on {principal} at {rate}% per year, compounded annually, for {years} years."
        solution = f"Apply the {factor}/100 growth factor each year, then subtract principal: {compute_answer(validator)}."
        template = "compound-interest-annual-v1"
        hints = ["Each year, apply the rate to the current amount.", "Compute P × (110/100)^years, then subtract P."]
    elif skill_id == "ratio-proportion":
        left, right = rng.randrange(1, 8), rng.randrange(1, 8)
        total = (left + right) * rng.randrange(2, 31)
        validator = {"kind": "expression", "expr": f"{total}*{left}//{left + right}"}
        prompt = f"A total of {total} is divided in the ratio {left}:{right}. How much is the first share?"
        solution = f"The first share is {left} of {left + right} equal parts: {compute_answer(validator)}."
        template = "ratio-share-v1"
        hints = ["Add the ratio terms to get the total number of parts.", "Multiply by the first term and divide by the sum of the terms."]
    elif skill_id == "averages":
        count, average = rng.choice((3, 4, 5)), rng.randrange(5, 81)
        total = count * average
        validator = {"kind": "expression", "expr": f"{total}//{count}"}
        prompt = f"The total of {count} values is {total}. What is their arithmetic mean?"
        solution = f"Mean equals total divided by count: {total}/{count} = {compute_answer(validator)}."
        template = "mean-from-total-v1"
        hints = ["Use mean = sum of values / number of values.", f"Divide {total} by {count}."]
    elif skill_id == "mixtures-alligations":
        left, right = rng.choice(((1, 2), (2, 1), (1, 3), (3, 1), (2, 3), (3, 2)))
        denominator = left + right
        base = rng.randrange(1, max(2, 100 // denominator))
        delta = rng.randrange(1, max(2, 100 // denominator - base + 1))
        low, high = base * denominator, (base + delta) * denominator
        validator = {"kind": "expression", "expr": f"({low}*{left}+{high}*{right})//{denominator}"}
        prompt = f"Mix {left} parts of a {low}% solution with {right} parts of a {high}% solution. What is the concentration?"
        solution = f"Use a weighted mean of the concentrations: {compute_answer(validator)}%."
        template = "mixture-weighted-concentration-v1"
        hints = ["Weight each concentration by the amount of that solution.", "Multiply concentration by parts, add, and divide by total parts."]
    elif skill_id == "partnership":
        capital_a, capital_b = rng.randrange(2, 11) * 1000, rng.randrange(2, 11) * 1000
        months_a, months_b = rng.choice(((12, 12), (12, 6), (6, 12), (9, 6), (6, 9)))
        share_a, share_b = capital_a * months_a, capital_b * months_b
        total_profit = (share_a + share_b) * rng.randrange(1, 6)
        validator = {"kind": "expression", "expr": f"{total_profit}*{share_a}//{share_a + share_b}"}
        prompt = f"A invests {capital_a} for {months_a} months; B invests {capital_b} for {months_b} months. How much of a {total_profit} profit goes to A?"
        solution = f"Profit follows capital × time; A receives {compute_answer(validator)}."
        template = "partnership-capital-time-v1"
        hints = ["Compute each partner's capital-month product.", "Divide the profit in the ratio of those products."]
    elif skill_id == "time-work":
        pairs = [(a, b) for a in range(2, 16) for b in range(2, 16)
                 if a != b and gcd(a, b) > 1]
        a_days, b_days = rng.choice(pairs)
        units = a_days * b_days // gcd(a_days, b_days)
        validator = {"kind": "expression", "expr": f"{units}//{a_days}+{units}//{b_days}"}
        prompt = f"A finishes a job in {a_days} days and B in {b_days} days. If it has {units} equal units, how many units do they complete together in one day?"
        solution = f"Add their daily rates: {units}/{a_days} + {units}/{b_days} = {compute_answer(validator)} units."
        template = "combined-work-rate-v1"
        hints = ["Convert each person's completion time into a daily work rate.", "Add the two rates using the stated work units."]
    else:
        raise ValueError(f"No safe practice template for {skill_id}")

    item_id = f"gen-{skill_id}-{serial:04d}"
    return {
        "id": item_id,
        "skill_id": skill_id,
        "family_id": item_id,
        "template_id": template,
        "purpose": "practice",
        "difficulty": f"Generated practice level {level}",
        "difficulty_level": level,
        "prompt": prompt,
        "answer": compute_answer(validator),
        "validator": validator,
        "solution": solution,
        "hints": hints,
        "reasoning_rubric": {"type": "integer_answer", "independent": True},
        "possible_misconception": "Draft: reviewer to identify the likely error for this item.",
        "follow_up": "Draft: reviewer to add a targeted follow-up.",
        "review_status": "draft",
        "provenance": f"Deterministic template {template}; seed-controlled generated numbers; requires human content review.",
    }


def generate_questions(skill_id: str, count: int, seed: int, existing: list[dict]) -> list[dict]:
    if type(count) is not int or count < 1:
        raise ValueError("count must be a positive integer")
    rng = random.Random(f"{seed}:{skill_id}")
    existing_ids = {item["id"] for item in existing}
    existing_prompts = {item["prompt"] for item in existing}
    used_ids = {int(match.group(1)) for qid in existing_ids
                if (match := re.fullmatch(rf"gen-{re.escape(skill_id)}-(\d+)", qid))}
    serial, generated = max(used_ids, default=0) + 1, []
    attempts = 0
    while len(generated) < count and attempts < count * 100:
        item = _candidate(skill_id, serial, rng)
        serial += 1
        attempts += 1
        if item["id"] in existing_ids or item["prompt"] in existing_prompts:
            continue
        item["generation"] = {
            "template_id": item["template_id"],
            "generator_version": "practice-drafts-v1",
            "seed": seed,
        }
        item["provenance"] += f" Seed={seed}."
        generated.append(item)
        existing_ids.add(item["id"])
        existing_prompts.add(item["prompt"])
    if len(generated) != count:
        raise ValueError(f"Only generated {len(generated)} unique drafts for {skill_id} after {attempts} attempts")
    return generated


def generate_assessment_questions(skill_id: str, seed: int, existing: list[dict]) -> list[dict]:
    """Create the 35-item draft assessment pool at the configured level split.

    Per level, visible diagnostic/verification items are split 15/10 overall;
    ten hidden items are reserved for two five-question validation forms.
    """
    diagnostic_by_level = {1: 2, 2: 3, 3: 5, 4: 4, 5: 1}
    verification_by_level = {1: 0, 2: 1, 3: 3, 4: 4, 5: 2}
    current_pool = [item for item in existing if item.get("skill_id") == skill_id
                    and item.get("purpose") in ("diagnostic", "verification")]
    current_audit = audit(current_pool, [skill_id])[skill_id]
    if current_audit["total"] == sum(TARGET_SPLIT.values()) and not current_audit["problems"]:
        return []
    rng = random.Random(f"{seed}:{skill_id}:assessment")
    prior_assessment = [item for item in existing if item.get("skill_id") == skill_id
                        and item.get("generation", {}).get("generator_version") == "assessment-drafts-v1"]
    if prior_assessment:
        raise ValueError(f"Assessment draft generation already exists for {skill_id}; review that set instead of duplicating it")
    existing_ids = {item["id"] for item in existing}
    existing_prompts = {item["prompt"] for item in existing}
    next_serial = 1
    generated = []
    for level in TARGET_SPLIT:
        for index in range(TARGET_SPLIT[level]):
            hidden = index < HIDDEN_SPLIT[level]
            purpose = "diagnostic" if hidden or index - HIDDEN_SPLIT[level] < diagnostic_by_level[level] else "verification"
            attempts = 0
            while attempts < 1000:
                item = _candidate(skill_id, next_serial, rng, level=level)
                item["id"] = f"gen-{skill_id}-assessment-{next_serial:04d}"
                item["family_id"] = item["id"]
                item["purpose"] = purpose
                item["hidden"] = hidden
                item["difficulty"] = f"Generated assessment draft level {level}"
                item["generation"] = {
                    "template_id": item["template_id"],
                    "generator_version": "assessment-drafts-v1",
                    "seed": seed,
                }
                item["provenance"] += f" Assessment draft generated with seed={seed}; requires independent human review."
                next_serial += 1
                attempts += 1
                if item["id"] in existing_ids or item["prompt"] in existing_prompts:
                    continue
                generated.append(item)
                existing_ids.add(item["id"])
                existing_prompts.add(item["prompt"])
                break
            else:
                raise ValueError(f"Could not generate a unique level-{level} item for {skill_id}")
    hidden_items = [item for item in generated if item["hidden"]]
    forms = split_forms(hidden_items)
    for item in hidden_items:
        item["validation_form"] = forms[item["id"]]
    return generated


def generate_review_questions(skill_id, count, seed, existing):
    """Fresh draft retention pool with provisional coverage facets for human review."""
    prior = [q for q in existing if q.get("skill_id") == skill_id and q.get("purpose") == "review"]
    needed = max(0, count - len(prior))
    if not needed:
        return []
    generated = generate_questions(skill_id, needed, seed, existing)
    from backend.numbers.distractors import PILOT_SKILLS, make_options
    for i, item in enumerate(generated, start=len(prior)):
        item["id"] = f"gen-{skill_id}-review-{i + 1:04d}"
        item["family_id"] = item["id"]
        item["purpose"] = "review"
        item["facet"] = ("basic", "combined", "constraints")[i % 3]
        item["generation"]["generator_version"] = "review-drafts-v1"
        item["generation"]["facets_provisional"] = True
        item["provenance"] += " Retention draft: a reviewer must check facet labels, genuine family separation and method coverage."
        if skill_id in PILOT_SKILLS:
            item["options"] = make_options(item)
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40, help="draft items to generate per supported skill")
    parser.add_argument("--seed", type=int, default=20261026, help="reproducible parameter seed")
    parser.add_argument("--skills", nargs="*", help="skill IDs; defaults to all supported arithmetic templates")
    parser.add_argument("--assessment", action="store_true",
                        help="generate a 35-item draft diagnostic, verification and hidden-form bank per selected skill")
    parser.add_argument("--review", action="store_true", help="fill a separate retention-review draft pool; use --count 9 for three three-item reviews")
    args = parser.parse_args()
    if args.assessment and args.review:
        parser.error("Choose --assessment or --review, not both.")
    document = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    skills = [skill["id"] for skill in load_curriculum()["skills"]]
    selected = args.skills or skills
    unknown = set(selected) - set(skills)
    if unknown:
        parser.error("unsupported skill(s): " + ", ".join(sorted(unknown)))
    generated = []
    for skill_id in selected:
        prior = document["questions"] + generated
        if args.assessment:
            generated.extend(generate_assessment_questions(skill_id, args.seed, prior))
        elif args.review:
            generated.extend(generate_review_questions(skill_id, args.count, args.seed, prior))
        else:
            generated.extend(generate_questions(skill_id, args.count, args.seed, prior))
    proposed = document["questions"] + generated
    errors = validate_bank(proposed)
    if errors:
        parser.error("generated items did not validate: " + "; ".join(errors))
    QUESTIONS.write_text(json.dumps({**document, "questions": proposed}, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    content_kind = "draft assessment questions" if args.assessment else "draft retention questions" if args.review else "draft practice questions"
    print(f"Added {len(generated)} {content_kind}; none were approved.")
    for skill_id in selected:
        print(f"  {skill_id}: {sum(item['skill_id'] == skill_id for item in generated)} drafts")
    print("Export the bank and have a human review the generated prompts, solutions, difficulty and hints before approval.")


if __name__ == "__main__":
    main()

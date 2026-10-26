"""Rule-based draft distractors for the ten arithmetic pilot topics.

These rules propose plausible errors and matching misconception tags. They are
not pedagogical evidence: question review must confirm each option and tag.
"""
from __future__ import annotations

import random
import re


PILOT_SKILLS = (
    "integer-properties", "percentages", "profit-loss", "simple-interest",
    "compound-interest", "ratio-proportion", "averages", "mixtures-alligations",
    "partnership", "time-work",
)

MISCONCEPTION_IDS = {
    "integer-properties": ("integer-parity-negative", "integer-inclusive-endpoints",
                           "integer-zero-parity", "integer-properties-calculation-slip"),
    "percentages": ("percent-forgot-divide-100", "percent-complement-confusion",
                    "percent-part-vs-new-total", "percentages-calculation-slip"),
    "profit-loss": ("profit-loss-direction-reversed", "profit-loss-amount-vs-price",
                    "profit-loss-base-confusion", "profit-loss-calculation-slip"),
    "simple-interest": ("simple-interest-percent-scale", "simple-interest-time-omitted",
                        "simple-vs-compound", "simple-interest-calculation-slip"),
    "compound-interest": ("compound-as-simple", "compound-amount-vs-interest",
                          "compound-time-missed", "compound-interest-calculation-slip"),
    "ratio-proportion": ("ratio-share-reversed", "ratio-total-parts-missed",
                         "ratio-total-not-recombined", "ratio-proportion-calculation-slip"),
    "averages": ("average-total-confusion", "average-count-off-by-one",
                 "average-missing-value-subtraction", "averages-calculation-slip"),
    "mixtures-alligations": ("mixture-unweighted-mean", "alligation-differences-not-crossed",
                             "mixture-concentration-vs-quantity", "mixtures-calculation-slip"),
    "partnership": ("partnership-time-ignored", "partnership-capital-ignored",
                    "partnership-ratio-misaligned", "partnership-calculation-slip"),
    "time-work": ("work-times-added", "work-reciprocal-confusion", "work-units-inconsistent",
                  "time-work-calculation-slip"),
}


def _prompt_numbers(prompt: str) -> list[int]:
    return [int(value) for value in re.findall(r"(?<![\w.])-?\d+", prompt)]


def proposed_distractors(question: dict) -> list[tuple[int, str]]:
    """Return three (wrong integer, hypothesis id) pairs for supported pilot items."""
    skill = question.get("skill_id")
    if skill not in MISCONCEPTION_IDS:
        raise ValueError(f"No reviewed distractor rule for {skill}")
    concepts = MISCONCEPTION_IDS[skill]
    answer = question.get("answer")
    if type(answer) is not int:
        raise ValueError(f"{question.get('id')}: distractor generation needs an integer answer")
    numbers = _prompt_numbers(question.get("prompt", ""))
    candidates = []
    if skill == "integer-properties":
        candidates = [(answer - 1, concepts[1]), (answer + 1, concepts[1]), (answer + 2, concepts[2])]
    elif skill == "percentages":
        rate, amount = numbers[:2]
        candidates = [(amount * rate, concepts[0]), (amount - answer, concepts[1]),
                      (amount + answer, concepts[2])]
    elif skill == "profit-loss":
        cost, rate = numbers[:2]
        change = cost * rate // 100
        profit = "profit" in question["prompt"]
        wrong_direction = cost - change if profit else cost + change
        wrong_base = cost * 100 // (100 - rate) if profit else cost * 100 // (100 + rate)
        candidates = [(wrong_direction, concepts[0]), (change, concepts[1]), (wrong_base, concepts[2])]
    elif skill == "simple-interest":
        principal, rate, years = numbers[:3]
        compound = principal * (100 + rate) ** years // (100 ** years) - principal
        candidates = [(principal * rate * years, concepts[0]),
                      (principal * rate // 100, concepts[1]), (compound, concepts[2])]
    elif skill == "compound-interest":
        principal, rate, years = numbers[:3]
        simple = principal * rate * years // 100
        one_fewer_period = principal * (100 + rate) ** max(0, years - 1) // (100 ** max(0, years - 1)) - principal
        candidates = [(simple, concepts[0]), (principal + answer, concepts[1]),
                      (one_fewer_period, concepts[2])]
    elif skill == "ratio-proportion":
        total, left, right = numbers[:3]
        candidates = [(total * right // (left + right), concepts[0]),
                      (total * left, concepts[1]), (total // 2, concepts[2])]
    elif skill == "averages":
        total, count = numbers[:2]
        candidates = [(total, concepts[0]), (total // (count + 1), concepts[1]),
                      (total // (count - 1), concepts[2])]
    elif skill == "mixtures-alligations":
        left, low, right, high = numbers[:4]
        denominator = left + right
        candidates = [((low + high) // 2, concepts[0]),
                      ((low * right + high * left) // denominator, concepts[1]),
                      (low, concepts[2])]
    elif skill == "partnership":
        capital_a, months_a, capital_b, months_b, profit = numbers[:5]
        capital_only = profit * capital_a // (capital_a + capital_b)
        time_only = profit * months_a // (months_a + months_b)
        candidates = [(capital_only, concepts[0]), (time_only, concepts[1]),
                      (profit // 2, concepts[2])]
    elif skill == "time-work":
        days_a, days_b, units = numbers[:3]
        candidates = [(days_a + days_b, concepts[0]), (units // days_a, concepts[1]),
                      (units // days_b, concepts[2])]

    result = []
    seen = {answer}
    for value, misconception_id in candidates:
        if type(value) is int and value not in seen:
            seen.add(value)
            result.append((value, misconception_id))
    if len(result) >= 3:
        return result[:3]
    for offset in (1, -1, 2, -2, 3, -3, 5, -5):
        value = answer + offset
        if value not in seen:
            seen.add(value)
            result.append((value, concepts[3]))
        if len(result) == 3:
            break
    if len(result) != 3:
        raise ValueError(f"{question.get('id')}: could not produce three distinct distractors")
    return result


def make_options(question: dict) -> list[dict]:
    answer = question["answer"]
    options = [{"id": "correct", "text": str(answer), "value": answer}]
    options.extend({"id": f"misconception-{index + 1}", "text": str(value), "value": value,
                    "misconception_id": misconception_id}
                   for index, (value, misconception_id) in enumerate(proposed_distractors(question)))
    random.Random(question["id"]).shuffle(options)
    return options

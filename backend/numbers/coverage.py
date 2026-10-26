"""C2/D7 bank rules: 35 questions per topic, mid-weighted, 10 hidden for validation.

Pure functions over question dictionaries (the questions.json format), so the same
checks run in tests, in scripts/question_bank.py and before import.
"""
from collections import Counter

LEVELS = (1, 2, 3, 4, 5)
TARGET_SPLIT = {1: 3, 2: 6, 3: 11, 4: 11, 5: 4}   # 35 per topic
HIDDEN_SPLIT = {1: 1, 2: 2, 3: 3, 4: 3, 5: 1}     # 10 per topic, two 5-question forms
TOTAL = sum(TARGET_SPLIT.values())
ASSESSMENT_PURPOSES = ("diagnostic", "verification")
FLAG_MIN_ANSWERS = 30     # automatic tag check once a question has this many answers
FLAG_TOLERANCE = 0.15     # observed vs predicted success rate gap that raises a flag


def in_bank(question):
    """Questions that count toward the 35: tagged assessment items that are not withdrawn."""
    return (question.get("purpose") in ASSESSMENT_PURPOSES and question.get("difficulty_level") in LEVELS
            and question.get("review_status") != "withdrawn")


def split_forms(hidden):
    """Snake-draft hidden questions by level into two parallel forms, A and B.

    With the 1/2/3/3/1 split this gives A = levels 1,3,3,4,4 and B = 2,2,3,4,5.
    """
    ordered = sorted(hidden, key=lambda q: (q["difficulty_level"], q["id"]))
    pattern = "ABBA"
    return {q["id"]: pattern[i % 4] for i, q in enumerate(ordered)}


def audit(questions, skills):
    """Per-topic coverage against D7. Returns {skill: report}; report["problems"] lists gaps."""
    reports = {}
    for skill in skills:
        items = [q for q in questions if q.get("skill_id") == skill and in_bank(q)]
        visible = Counter(q["difficulty_level"] for q in items if not q.get("hidden"))
        hidden = Counter(q["difficulty_level"] for q in items if q.get("hidden"))
        families = Counter(q["family_id"] for q in items)
        problems = []
        for level in LEVELS:
            have, want = visible[level] + hidden[level], TARGET_SPLIT[level]
            if have != want:
                problems.append(f"level {level}: {have} questions, target {want}")
            if hidden[level] != HIDDEN_SPLIT[level]:
                problems.append(f"level {level}: {hidden[level]} hidden, target {HIDDEN_SPLIT[level]}")
        repeated = sorted(f for f, n in families.items() if n > 1)
        if repeated:
            problems.append("families used more than once: " + ", ".join(repeated))
        forms = Counter(q.get("validation_form") for q in items if q.get("hidden"))
        if hidden and (forms.get("A", 0) != 5 or forms.get("B", 0) != 5):
            problems.append(f"validation forms A/B have {forms.get('A', 0)}/{forms.get('B', 0)} questions, target 5/5")
        if any(q.get("validation_form") and not q.get("hidden") for q in items):
            problems.append("a visible question carries a validation form")
        approved = sum(q.get("review_status") == "approved" for q in items)
        reports[skill] = {
            "total": len(items), "target": TOTAL, "approved": approved,
            "by_level": {lv: visible[lv] + hidden[lv] for lv in LEVELS},
            "hidden_by_level": {lv: hidden[lv] for lv in LEVELS},
            "problems": problems,
        }
    return reports


def flag_tags(rows):
    """Automatic tag check (D7). rows: (question_id, level, predicted, correct) per new-version answer.

    A question is flagged once it has FLAG_MIN_ANSWERS answers and its observed success rate
    differs from the mean prediction by more than FLAG_TOLERANCE. The direction says whether the
    tag looks too hard (learners do better than predicted) or too easy.
    """
    grouped = {}
    for qid, level, predicted, correct in rows:
        if predicted is None:
            continue
        entry = grouped.setdefault(qid, {"level": level, "n": 0, "predicted": 0.0, "correct": 0})
        entry["n"] += 1
        entry["predicted"] += predicted
        entry["correct"] += bool(correct)
    flags = []
    for qid, e in sorted(grouped.items()):
        if e["n"] < FLAG_MIN_ANSWERS:
            continue
        observed, predicted = e["correct"] / e["n"], e["predicted"] / e["n"]
        if abs(observed - predicted) > FLAG_TOLERANCE:
            flags.append({"question_id": qid, "level": e["level"], "answers": e["n"],
                          "observed": round(observed, 3), "predicted": round(predicted, 3),
                          "suggestion": "tag may be too hard" if observed > predicted else "tag may be too easy"})
    return flags

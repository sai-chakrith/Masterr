import copy
import unittest
from unittest.mock import patch

from backend.numbers.bank import (
    compute_answer, load_curriculum, load_questions, select_question,
    student_view, validate_bank,
)


class NumbersTests(unittest.TestCase):
    def test_seed_bank_arithmetic(self):
        self.assertEqual(validate_bank(), [])

    def test_prerequisites_exist_and_are_acyclic(self):
        skills = {s["id"]: s for s in load_curriculum()["skills"]}
        def visit(skill_id, path):
            self.assertNotIn(skill_id, path)
            for prerequisite in skills[skill_id]["prerequisites"]:
                self.assertIn(prerequisite, skills)
                visit(prerequisite, path | {skill_id})
        for skill_id in skills:
            visit(skill_id, set())

    def test_integer_edge_cases(self):
        self.assertEqual(compute_answer({"kind": "even_count", "low": -4, "high": 0}), 3)
        self.assertEqual(compute_answer({"kind": "prime_count", "values": [-3, 0, 1, 2, 25]}), 1)
        self.assertEqual(compute_answer({"kind": "factor_count", "number": 1}), 1)
        self.assertEqual(compute_answer({"kind": "factor_count", "number": 49}), 3)
        self.assertEqual(compute_answer({"kind": "remainder", "number": -1, "divisor": 5}), 4)
        self.assertEqual(compute_answer({"kind": "power_remainder", "base": 2, "exponent": 0, "divisor": 10}), 1)

    def test_ambiguous_digit_question_rejected(self):
        with self.assertRaises(ValueError):
            compute_answer({"kind": "missing_digit", "pattern": "4?2", "divisor": 3})

    def test_wrong_answer_and_duplicate_rejected(self):
        question = copy.deepcopy(load_questions()[0])
        question["answer"] = 999
        self.assertTrue(validate_bank([question]))
        question = load_questions()[0]
        self.assertTrue(validate_bank([question, question]))

    def test_drafts_are_not_served(self):
        self.assertIsNone(select_question("integer-properties", "diagnostic"))

    def test_freshness_is_by_family(self):
        question = copy.deepcopy(load_questions()[0])
        question.pop("options", None)  # This test covers family freshness, not MCQ review gates.
        question["review_status"] = "approved"
        # Synthetic review metadata is a test fixture, never a real approval.
        question["review"] = {"reviewer": "test-fixture", "date": "test-fixture"}
        with patch("backend.numbers.bank.load_questions", return_value=[question]):
            self.assertEqual(select_question(question["skill_id"], "diagnostic"), question)
            self.assertIsNone(select_question(question["skill_id"], "diagnostic", [question["family_id"]]))

    def test_answer_key_is_not_in_student_payload(self):
        view = student_view(load_questions()[0])
        self.assertEqual(set(view), {"id", "skill_id", "prompt", "difficulty"})


if __name__ == "__main__":
    unittest.main()


class ExpressionValidatorTests(unittest.TestCase):
    def test_helpers_compute_known_values(self):
        from backend.numbers.bank import evaluate
        self.assertEqual(evaluate("multiples(1,100,7)"), 14)
        self.assertEqual(evaluate("factor_count(360)"), 24)
        self.assertEqual(evaluate("smallest_with_remainders(3,2,5,3,7,2)"), 23)
        self.assertEqual(evaluate("trailing_zeros_factorial(100)"), 24)

    def test_rejects_anything_but_integer_arithmetic(self):
        from backend.numbers.bank import evaluate
        for expr in ('__import__("os")', "open(1)", "(1).real", "1/2", "[1]", "2**100", "x", "1.5", "'a'"):
            with self.assertRaises((ValueError, SyntaxError)):
                evaluate(expr)


class DraftBankTests(unittest.TestCase):
    def test_every_topic_meets_the_d7_split(self):
        from backend.numbers.coverage import audit
        skills = [s["id"] for s in load_curriculum()["skills"]]
        for skill, report in audit(load_questions(), skills).items():
            self.assertEqual(report["problems"], [], skill)
            self.assertEqual(report["total"], 35, skill)

    def test_draft_bank_is_not_approved(self):
        bank = [q for q in load_questions() if q.get("difficulty_level")]
        self.assertTrue(bank)
        self.assertTrue(all(q["review_status"] == "draft" for q in bank))

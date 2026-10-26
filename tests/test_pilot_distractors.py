from backend.numbers.bank import load_misconceptions, load_questions, validate_bank
from backend.numbers.distractors import PILOT_SKILLS
from scripts.add_distractors import attach_options


def test_pilot_questions_have_four_distinct_options_and_reviewable_tags():
    questions = [q for q in load_questions() if q["skill_id"] in PILOT_SKILLS]
    misconceptions = {item["id"]: item for item in load_misconceptions()}
    assert questions
    for question in questions:
        options = question["options"]
        assert len(options) == 4
        assert len({option["value"] for option in options}) == 4
        assert sum(option["value"] == question["answer"] for option in options) == 1
        for option in options:
            if option["value"] != question["answer"]:
                misconception = misconceptions[option["misconception_id"]]
                assert misconception["skill_id"] == question["skill_id"]
                assert misconception["review_status"] == "draft"


def test_attaching_draft_options_is_idempotent_and_validates_bank():
    updated, changed = attach_options({"questions": load_questions()})
    assert changed == []
    assert validate_bank(updated["questions"]) == []

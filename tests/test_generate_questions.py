from backend.numbers.bank import load_questions, validate_bank
from backend.numbers.coverage import audit
from scripts.generate_questions import generate_assessment_questions, generate_questions


def test_generator_produces_valid_unpublished_practice_for_current_skills():
    source = load_questions()
    skills = {question["skill_id"] for question in source}
    generated = []
    for skill_id in sorted(skills):
        generated.extend(generate_questions(skill_id, 5, 321, source + generated))

    assert len(generated) == 5 * len(skills)
    assert all(question["purpose"] == "practice" for question in generated)
    assert all(question["review_status"] == "draft" for question in generated)
    assert all(question["generation"]["seed"] == 321 for question in generated)
    assert len({question["id"] for question in generated}) == len(generated)
    assert validate_bank(source + generated) == []


def test_generator_rejects_unsupported_skill():
    try:
        generate_questions("seating-arrangement", 1, 1, [])
    except ValueError as exc:
        assert "No safe practice template" in str(exc)
    else:
        raise AssertionError("unsupported skills must not get guessed templates")


def test_proposal_pilot_assessment_pools_match_weighted_bank_rules():
    source = load_questions()
    pilot_skills = (
        "integer-properties", "percentages", "profit-loss", "simple-interest",
        "compound-interest", "ratio-proportion", "averages", "mixtures-alligations",
        "partnership", "time-work",
    )
    new_pilot_skills = set(pilot_skills[1:])
    base = [item for item in source if not (
        item["skill_id"] in new_pilot_skills
        and item.get("purpose") in ("diagnostic", "verification")
    )]
    generated = []
    for skill_id in pilot_skills[1:]:
        generated.extend(generate_assessment_questions(skill_id, 20261026, base + generated))

    bank = base + generated
    assert validate_bank(bank) == []
    reports = audit(bank, pilot_skills)
    assert all(not reports[skill_id]["problems"] for skill_id in pilot_skills)
    assert all(reports[skill_id]["approved"] == 0 for skill_id in pilot_skills[1:])
    assert all(sum(item["skill_id"] == skill_id for item in generated) == 35
               for skill_id in pilot_skills[1:])

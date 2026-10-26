"""C2 tag flags, C5 pilot split, K5/S5 analysis maths and the validation API route."""
import pytest

from backend.numbers.coverage import flag_tags, split_forms
from scripts import pilot_analysis as pa
from scripts.pilot import PILOT_SKILL_IDS, SKILL_IDS, split_practice_topics, split_topics


def test_pilot_split_gives_half_the_topics_the_new_design():
    first = split_topics("learner-1", "seed")
    assert sum(v == "new" for v in first.values()) == len(SKILL_IDS) // 2
    assert split_topics("learner-1", "seed") == first           # stable per learner
    patterns = {tuple(split_topics(f"learner-{i}", "seed").values()) for i in range(30)}
    assert len(patterns) > 5                                       # random across learners


def test_personalised_practice_split_is_stable_and_balanced():
    skills = [f"topic-{i}" for i in range(10)]
    first = split_practice_topics("learner-1", "seed", skills)
    assert sum(value == "personalised" for value in first.values()) == 5
    assert sum(value == "fixed" for value in first.values()) == 5
    assert split_practice_topics("learner-1", "seed", skills) == first


def test_default_personalisation_pilot_targets_the_proposed_ten_topics():
    assert len(PILOT_SKILL_IDS) == 10
    assert set(PILOT_SKILL_IDS) <= set(SKILL_IDS)
    assignment = split_practice_topics("learner-1", "seed", PILOT_SKILL_IDS)
    assert len(assignment) == 10
    assert sum(value == "personalised" for value in assignment.values()) == 5


def test_split_forms_balances_levels():
    hidden = [{"id": f"q{i}", "difficulty_level": lv} for i, lv in enumerate([1, 2, 2, 3, 3, 3, 4, 4, 4, 5])]
    forms = split_forms(hidden)
    a = sorted(q["difficulty_level"] for q in hidden if forms[q["id"]] == "A")
    b = sorted(q["difficulty_level"] for q in hidden if forms[q["id"]] == "B")
    assert a == [1, 3, 3, 4, 4] and b == [2, 2, 3, 4, 5]


def test_tag_flags_need_thirty_answers_and_a_real_gap():
    rows = [("easy-tagged-hard", 4, 0.3, True)] * 25 + [("easy-tagged-hard", 4, 0.3, False)] * 5
    rows += [("fine", 3, 0.5, i % 2 == 0) for i in range(40)]
    rows += [("few", 3, 0.5, True)] * 10
    flags = flag_tags(rows)
    assert [f["question_id"] for f in flags] == ["easy-tagged-hard"]
    assert flags[0]["suggestion"] == "tag may be too hard"


def row(learner, skill, correct, predicted=None, source="practice", stage=None, version="new", t="2026-11-01"):
    return {"learner": learner, "skill": skill, "correct": correct, "predicted": predicted, "source": source,
            "stage": stage, "session_status": "completed", "created_at": t, "version": version,
            "dont_know": False, "duration_ms": 60000, "assistance": "independent", "level": 3}


def test_calibration_compares_predicted_with_actual():
    rows = [row("a", "s", i < 75, predicted=0.75) for i in range(100)]
    table, gap = pa.calibration(rows)
    assert table[0]["n"] == 100 and table[0]["actual"] == pytest.approx(0.75)
    assert gap == pytest.approx(0.0)


def test_learning_curve_counts_attempt_order_per_learner():
    rows = [row("a", "s", False, t="1"), row("a", "s", True, t="2"), row("b", "s", False, t="1"),
            row("b", "s", False, t="2")]
    assert pa.learning_curves(rows)["s"] == [(1, 1.0, 2), (2, 0.5, 2)]


def test_normalised_gain_and_paired_effect():
    assert pa.normalised_gain(40, 70) == pytest.approx(0.5)
    assert pa.normalised_gain(100, 100) is None
    scores = {}
    versions = {}
    for i, (new_post, cur_post) in enumerate([(80, 60), (100, 60), (60, 60), (80, 40)]):
        scores[(f"l{i}", "x")] = {"pre": 20, "post": new_post}
        scores[(f"l{i}", "y")] = {"pre": 20, "post": cur_post}
        versions[(f"l{i}", "x")], versions[(f"l{i}", "y")] = "new", "current"
    gain_rows = pa.gains(scores, versions)
    effect = pa.paired_effect(gain_rows)
    assert effect["learners"] == 4 and effect["mean_difference"] == pytest.approx(0.3125)  # (0.25 + 0.5 + 0 + 0.5) / 4
    assert effect["dz"] > 0


def test_validation_scores_and_label_outcomes():
    rows = [row("a", "s", c, source="validation", stage="delayed") for c in (True, True, True, False)]
    scores = pa.validation_scores(rows)
    assert scores[("a", "s")]["delayed"] == 75.0
    assert pa.label_outcomes(scores, {("a", "s"): "resolved"}) == {"resolved": {"n": 1, "mean": 75.0}}


def test_report_renders_without_data():
    text, calibration_svg, curves_svg = pa.report([], [], {}, {})
    assert "Stage 1" in text and calibration_svg.startswith("<svg") and curves_svg.startswith("<svg")

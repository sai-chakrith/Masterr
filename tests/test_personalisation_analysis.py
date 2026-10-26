import pytest

from scripts.personalisation_analysis import normalized_gain, paired_strategy_effect, report


def test_normalized_gain_handles_perfect_pretest():
    assert normalized_gain(50, 75) == 0.5
    assert normalized_gain(100, 100) is None


def test_strategy_effect_pairs_conditions_within_each_learner():
    rows = [
        {"learner": "a", "strategy": "personalised", "gain": 0.5},
        {"learner": "a", "strategy": "fixed", "gain": 0.3},
        {"learner": "b", "strategy": "personalised", "gain": 0.4},
        {"learner": "b", "strategy": "fixed", "gain": 0.3},
        {"learner": "c", "strategy": "personalised", "gain": 0.9},
    ]
    result = paired_strategy_effect(rows)
    assert result["learners"] == 2
    assert result["mean_difference"] == pytest.approx(0.15)
    assert result["dz"] is not None


def test_strategy_effect_reports_missing_pairs_without_inventing_effect():
    result = paired_strategy_effect([{"learner": "a", "strategy": "fixed", "gain": 0.2}])
    assert result == {"learners": 0, "mean_difference": None, "dz": None, "t": None}


def test_report_uses_assigned_pairs_as_denominator_for_missing_forms():
    assignments = [
        {"learner": "a", "skill": "percentages", "strategy": "personalised"},
        {"learner": "b", "skill": "percentages", "strategy": "fixed"},
    ]
    stages = {("a", "percentages"): {"pre", "post"},
              ("b", "percentages"): {"pre"}}
    text = report([], [], {}, [], assignments, stages)
    assert "| personalised | 1 | 1 | 1 | 0 | 0 | 0 | 1 |" in text
    assert "| fixed | 1 | 1 | 0 | 0 | 0 | 1 | 1 |" in text
    assert "percentages: personalised 1, fixed 1" in text

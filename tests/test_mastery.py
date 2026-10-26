"""K1/K3: the scoring engine against the proposal's points table and decision rules."""
import itertools
import random

import pytest

from backend import mastery as m

# Points per answer for a learner at rating 0 with K = 1 (proposal, "How the score is calculated").
POINTS = [
    (2, 0.73, 0.27, -0.73, -0.48),
    (3, 0.50, 0.50, -0.50, -0.25),
    (4, 0.27, 0.73, -0.27, -0.02),
]


@pytest.mark.parametrize("level,expected,right,wrong,dont_know", POINTS)
def test_points_table(level, expected, right, wrong, dont_know):
    assert round(m.expected(0.0, level), 2) == expected
    for result, points in ((m.RIGHT, right), (m.WRONG, wrong), (m.DONT_KNOW, dont_know)):
        step = m.update(0.0, 0, [], level, result)
        assert step.k == 1.0
        assert round(step.change, 2) == points


def test_dont_know_never_raises_the_score():
    # Level 5 expects 12%, below the 0.25 credit: the change is capped at zero.
    assert m.update(0.0, 0, [], 5, m.DONT_KNOW).change == 0.0
    for rating in (-3.0, -1.0, 0.0, 2.0):
        for level in range(1, 6):
            assert m.update(rating, 10, [], level, m.DONT_KNOW).change <= 0.0


def test_dont_know_costs_a_blind_guess_on_average():
    for level in range(1, 5):
        guess = 0.25 * m.update(0.0, 0, [], level, m.RIGHT).change + 0.75 * m.update(0.0, 0, [], level, m.WRONG).change
        assert m.update(0.0, 0, [], level, m.DONT_KNOW).change == pytest.approx(guess)


def test_shown_score_landmarks():
    assert m.shown_score(0.0) == 0.5
    assert round(m.shown_score(1.1), 2) == 0.75
    assert round(m.shown_score(2.0), 2) == 0.88
    assert m.rating_for(0.75) == pytest.approx(1.0986, abs=1e-4)


def test_step_size_schedule():
    assert m.step_size(0, []) == 1.0
    assert m.step_size(4, [0.1, 0.1, 0.1, 0.1]) == 1.0
    assert m.step_size(5, [0.2, 0.1, 0.3, 0.1]) == 0.8
    assert m.step_size(5, [-0.2, -0.1, -0.3, -0.1]) == 0.8
    assert m.step_size(5, [0.2, -0.1, 0.3, 0.1]) == 0.3
    assert m.step_size(5, [0.2, 0.1, 0.3]) == 0.3
    assert m.step_size(9, [0.2, 0.0, 0.3, 0.1]) == 0.3


def test_update_keeps_last_four_changes():
    rating, count, recent = 0.0, 0, []
    for _ in range(7):
        step = m.update(rating, count, recent, 3, m.RIGHT)
        rating, count, recent = step.rating, step.answer_count, step.recent_changes
    assert count == 7 and len(recent) == 4 and all(c > 0 for c in recent)


def test_rescore_is_order_free():
    assert m.rescore([(3, m.RIGHT)] * 3 + [(3, m.WRONG)] * 3) == pytest.approx(0.0, abs=1e-9)
    assert m.rescore([(3, m.WRONG)] * 3 + [(3, m.RIGHT)] * 3) == pytest.approx(0.0, abs=1e-9)
    answers = [(3, m.RIGHT), (4, m.WRONG), (3, m.DONT_KNOW), (4, m.RIGHT), (3, m.RIGHT), (4, m.RIGHT),
               (3, m.WRONG), (4, m.RIGHT)]
    reference = m.decide(answers)
    rng = random.Random(1)
    for _ in range(50):
        shuffled = answers[:]
        rng.shuffle(shuffled)
        decision = m.decide(shuffled)
        assert decision.status == reference.status
        assert decision.rating == pytest.approx(reference.rating, abs=1e-9)


def test_rescore_pulls_short_streaks_towards_the_middle():
    # Eight right answers cannot produce an infinite rating; the prior keeps it finite.
    theta = m.rescore([(m.diagnostic_level(i), m.RIGHT) for i in range(8)])
    assert 1.5 < theta < 4


def levels(n):
    return [m.diagnostic_level(i) for i in range(n)]


def test_decision_safety_zone():
    assert m.decide([(lv, m.RIGHT) for lv in levels(7)]).status == "continue"
    assert m.decide([(lv, m.RIGHT) for lv in levels(8)]).status == "mastered"
    assert m.decide([(lv, m.WRONG) for lv in levels(8)]).status == "gap"
    in_between = [(lv, m.RIGHT if i % 4 else m.WRONG) for i, lv in enumerate(levels(8))]
    decision = m.decide(in_between)
    assert decision.status == "continue" and m.GAP_LINE <= decision.score < m.MASTERED_LINE
    longer = [(lv, m.RIGHT if i % 4 else m.WRONG) for i, lv in enumerate(levels(12))]
    assert m.decide(longer).status == "borderline"


def test_cut_offs_have_the_stated_meaning():
    # Every pattern of 8 alternating answers decides consistently with its re-scored value.
    for pattern in itertools.product((m.RIGHT, m.WRONG), repeat=8):
        decision = m.decide(list(zip(levels(8), pattern)))
        if decision.status == "mastered":
            assert decision.score >= 0.88
        elif decision.status == "gap":
            assert decision.score < 0.60
        else:
            assert 0.60 <= decision.score < 0.88


@pytest.mark.parametrize("right,dont_know,passed", [(6, 0, False), (7, 0, True), (10, 0, True), (0, 10, False), (6, 4, False)])
def test_retest_rule(right, dont_know, passed):
    results = [m.RIGHT] * right + [m.DONT_KNOW] * dont_know
    results += [m.WRONG] * (10 - len(results))
    assert m.retest_passed(results) is passed


def test_retest_needs_exactly_ten():
    assert not m.retest_passed([m.RIGHT] * 9)


def test_difficulty_rejects_untagged_levels():
    for bad in (0, 6, None, 3.0):
        with pytest.raises(ValueError):
            m.difficulty(bad)

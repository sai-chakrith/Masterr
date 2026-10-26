"""Track 1 scoring engine (D1-D4): Elo running score, "I don't know", re-score and decision.

Published names used by other tracks: ``update``, ``rescore``, ``decide`` plus the
constants below. Everything here is pure arithmetic with no database access, so the
same code drives the API, the simulation (scripts/convergence_study.py) and tests.

Scale: a rating is in logits. Shown score = 1 / (1 + e^-rating) = the predicted chance
of solving a typical (level-3) question. Difficulty tags 1-5 map to -2..+2.
"""
from dataclasses import dataclass
from math import exp, log

RIGHT, WRONG, DONT_KNOW = "right", "wrong", "dont_know"
RESULT_VALUE = {RIGHT: 1.0, WRONG: 0.0, DONT_KNOW: 0.25}  # 0.25 = blind guess on 4 options

BAR = 0.75            # D3: mastered = solves 75% of typical questions (per-topic override allowed)
MASTERED_LINE = 0.88  # D4: re-scored diagnostic at or above this is Mastered
GAP_LINE = 0.60       # D4: re-scored diagnostic below this is Gap
DIAGNOSTIC_MIN = 8
DIAGNOSTIC_MAX = 12
DIAGNOSTIC_LEVELS = (3, 4)  # alternate near the bar
RETEST_SIZE = 10
RETEST_PASS = 7

K_START, K_TREND, K_SETTLED = 1.0, 0.8, 0.3
START_ANSWERS = 5   # K_START for a learner's first five answers on a topic
TREND_WINDOW = 4    # K_TREND when the last four changes all went the same way
PRIOR_SD = 1.5      # mild pull towards the middle in the re-score (tuned in K2)


def difficulty(level):
    if type(level) is not int or not 1 <= level <= 5:
        raise ValueError("Difficulty level must be an integer from 1 to 5")
    return float(level - 3)


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + exp(-x))
    z = exp(x)
    return z / (1.0 + z)


def expected(rating, level):
    """Predicted chance of a right answer to a question with this difficulty tag."""
    return sigmoid(rating - difficulty(level))


def shown_score(rating):
    return sigmoid(rating)


def rating_for(score):
    if not 0 < score < 1:
        raise ValueError("Score must be strictly between 0 and 1")
    return log(score / (1 - score))


def step_size(answer_count, recent_changes):
    if answer_count < START_ANSWERS:
        return K_START
    last = list(recent_changes)[-TREND_WINDOW:]
    if len(last) == TREND_WINDOW and (all(c > 0 for c in last) or all(c < 0 for c in last)):
        return K_TREND
    return K_SETTLED


@dataclass(frozen=True)
class Update:
    rating: float
    change: float
    k: float
    expected: float
    answer_count: int
    recent_changes: list


def update(rating, answer_count, recent_changes, level, result):
    """One Elo step. "I don't know" counts 0.25 and its change is capped at 0."""
    if result not in RESULT_VALUE:
        raise ValueError("Unknown result")
    p = expected(rating, level)
    k = step_size(answer_count, recent_changes)
    change = k * (RESULT_VALUE[result] - p)
    if result == DONT_KNOW:
        change = min(change, 0.0)
    recent = (list(recent_changes) + [round(change, 6)])[-TREND_WINDOW:]
    return Update(rating + change, change, k, p, answer_count + 1, recent)


def rescore(answers, prior_sd=PRIOR_SD):
    """Single rating that best explains all answers together (MAP, normal prior at 0).

    ``answers`` is an iterable of (level, result). Order never matters.
    """
    data = [(difficulty(level), RESULT_VALUE[result]) for level, result in answers]
    precision = 1.0 / (prior_sd * prior_sd)
    theta = 0.0
    for _ in range(100):  # Newton on a strictly concave objective
        grad = -theta * precision
        curv = -precision
        for d, r in data:
            p = sigmoid(theta - d)
            grad += r - p
            curv -= p * (1 - p)
        step = grad / curv
        theta -= step
        if abs(step) < 1e-10:
            break
    return theta


@dataclass(frozen=True)
class Decision:
    status: str   # "continue", "mastered", "borderline" or "gap"
    rating: float
    score: float
    answers: int


def decide(answers, prior_sd=PRIOR_SD, mastered_line=MASTERED_LINE, gap_line=GAP_LINE):
    """D4 safety zone: decide after 8 answers, extend one at a time up to 12."""
    answers = list(answers)
    theta = rescore(answers, prior_sd)
    score = shown_score(theta)
    n = len(answers)
    if n < DIAGNOSTIC_MIN:
        status = "continue"
    elif score >= mastered_line:
        status = "mastered"
    elif score < gap_line:
        status = "gap"
    elif n >= DIAGNOSTIC_MAX:
        status = "borderline"
    else:
        status = "continue"
    return Decision(status, theta, score, n)


def retest_passed(results):
    """D6: pass at 7/10; "I don't know" is never correct."""
    results = list(results)
    return len(results) == RETEST_SIZE and sum(r == RIGHT for r in results) >= RETEST_PASS


def diagnostic_level(position):
    """Target level for the n-th diagnostic question (0-based): 3, 4, 3, 4, ..."""
    return DIAGNOSTIC_LEVELS[position % len(DIAGNOSTIC_LEVELS)]

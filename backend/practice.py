"""Deterministic practice selection and progress rules for the personalised policy."""
from __future__ import annotations

from dataclasses import dataclass

from backend.mastery import expected, rating_for, shown_score

PRACTICE_POLICY = "adaptive-practice-v1"
FIXED_PRACTICE_POLICY = "fixed-practice-v1"
PRACTICE_BLOCK_SIZE = 10
MIN_PRACTICE_BEFORE_RETEST = 5
STUCK_AFTER = 10
NO_PROGRESS_WINDOW = 5
TARGET_SUCCESS = 0.80


def target_difficulty(rating: float, target_success: float = TARGET_SUCCESS) -> int:
    """Choose the nearest 1-5 question level predicted to yield target success."""
    if not 0 < target_success < 1:
        raise ValueError("target_success must be between zero and one")
    # expected(rating, level) >= target means level <= 3 + rating - logit(target).
    level = round(3 + rating - rating_for(target_success))
    return max(1, min(5, level))


def select_adaptive_questions(questions, rating: float, count: int = PRACTICE_BLOCK_SIZE):
    """Pick unique, fresh question families nearest the 80% success level."""
    if count < 1:
        raise ValueError("count must be positive")
    target = target_difficulty(rating)
    candidates = sorted(
        (q for q in questions if q.difficulty_level is not None and not q.hidden),
        key=lambda q: (abs(q.difficulty_level - target),
                       abs(expected(rating, q.difficulty_level) - TARGET_SUCCESS), q.id),
    )
    result, families = [], set()
    for question in candidates:
        if question.family_id in families:
            continue
        result.append(question)
        families.add(question.family_id)
        if len(result) == count:
            break
    return result


def select_fixed_questions(questions, count: int = PRACTICE_BLOCK_SIZE):
    """Pick a mixed-level comparison block, with nearest-level fallback."""
    pool = [q for q in questions if q.difficulty_level is not None and not q.hidden]
    seen, selected = set(), []
    for position in range(count):
        target = (position % 5) + 1
        candidates = sorted(pool, key=lambda q: (abs(q.difficulty_level - target), q.id))
        item = next((q for q in candidates if q.family_id not in seen), None)
        if item is None:
            break
        selected.append(item)
        seen.add(item.family_id)
    return selected


@dataclass(frozen=True)
class PracticeProgress:
    count: int
    best_score: float
    recent_scores: tuple[float, ...]
    stuck: bool
    ready_for_retest: bool


def update_progress(*, count: int, best_score: float | None, recent_scores,
                    score: float, mastery_bar: float) -> PracticeProgress:
    """Track no-progress episodes; never changes assessment status or rating."""
    new_count = count + 1
    best = max(best_score if best_score is not None else score, score)
    recent = tuple((*recent_scores, score)[-NO_PROGRESS_WINDOW:])
    no_rise = len(recent) == NO_PROGRESS_WINDOW and max(recent) <= recent[0]
    stuck = new_count >= STUCK_AFTER and best < mastery_bar and no_rise
    return PracticeProgress(
        count=new_count, best_score=best, recent_scores=recent, stuck=stuck,
        ready_for_retest=new_count >= MIN_PRACTICE_BEFORE_RETEST and score >= mastery_bar,
    )


def review_days_after_pass(occasion: int) -> int | None:
    """Return the interval for the next review occasion, or None when complete."""
    schedule = (3, 7, 21)
    return schedule[occasion] if 0 <= occasion < len(schedule) else None


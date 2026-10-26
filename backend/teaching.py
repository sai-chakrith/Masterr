"""Learner-band teaching decisions kept separate from assessment status."""
from __future__ import annotations


def teaching_mode(score: float | None) -> str:
    """Select guidance using the proposal's bands; no evidence starts with examples."""
    if score is not None and not 0 <= score <= 1:
        raise ValueError("score must be between zero and one")
    if score is None or score < 0.50:
        return "worked_examples"
    if score <= 0.75:
        return "hinted_practice"
    return "practice_first"


def teaching_plan(skill: dict, score: float | None, curriculum_status: str) -> dict:
    mode = teaching_mode(score)
    published = curriculum_status == "approved"
    return {
        "mode": mode,
        "score": score,
        "content_available": published,
        "objective": skill.get("objective") if published else None,
        "lesson": skill.get("lesson") if published and mode == "worked_examples" else None,
        "worked_example": skill.get("worked_example") if published and mode == "worked_examples" else None,
        "half_worked_example": skill.get("half_worked_example")
        if published and mode == "worked_examples" else None,
        "hints_available": published and mode == "hinted_practice",
        "explanation_after_mistake": published and mode == "practice_first",
    }

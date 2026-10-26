"""Reviewed exam-profile definitions for goal-to-topic routing."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date

from backend.curriculum import load_curriculum

EXAM_PROFILES_PATH = Path(__file__).resolve().parents[1] / "content" / "numbers" / "exam_profiles.json"


class ExamProfileError(ValueError):
    pass


def load_exam_profiles(path: Path = EXAM_PROFILES_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExamProfileError(f"Unable to load exam profiles: {exc}") from exc
    problems = validate_exam_profiles(data)
    if problems:
        raise ExamProfileError("; ".join(problems))
    return data


def validate_exam_profiles(data: dict, curriculum: dict | None = None) -> list[str]:
    if not isinstance(data, dict):
        return ["profile document must be an object"]
    if type(data.get("schema_version")) is not int or data["schema_version"] < 1:
        return ["schema_version must be a positive integer"]
    if data.get("status") not in {"draft", "approved"}:
        return ["status must be draft or approved"]
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        return ["profiles must be a list"]
    curriculum = curriculum or load_curriculum()
    known_skills = {skill["id"] for skill in curriculum["skills"]}
    errors, seen = [], set()
    for profile in profiles:
        if not isinstance(profile, dict):
            errors.append("every profile must be an object")
            continue
        profile_id, name = profile.get("id"), profile.get("name")
        if not isinstance(profile_id, str) or not profile_id or profile_id in seen:
            errors.append(f"profile {profile_id!r}: IDs must be present and unique")
            continue
        seen.add(profile_id)
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{profile_id}: name is required")
        targets = profile.get("target_skill_ids")
        if (not isinstance(targets, list) or not targets
                or any(not isinstance(skill_id, str) for skill_id in targets)):
            errors.append(f"{profile_id}: target_skill_ids must be a non-empty list")
        elif len(targets) != len(set(targets)) or set(targets) - known_skills:
            errors.append(f"{profile_id}: targets must be unique known curriculum skills")
        default_bar = profile.get("default_mastery_bar", 0.75)
        if type(default_bar) not in (int, float) or not 0.5 <= default_bar <= 0.95:
            errors.append(f"{profile_id}: default_mastery_bar must be from 0.50 to 0.95")
        topic_bars = profile.get("topic_bars", {})
        if not isinstance(topic_bars, dict):
            errors.append(f"{profile_id}: topic_bars must be an object")
        else:
            for skill_id, bar in topic_bars.items():
                if skill_id not in known_skills:
                    errors.append(f"{profile_id}: unknown topic bar {skill_id}")
                if type(bar) not in (int, float) or not 0.5 <= bar <= 0.95:
                    errors.append(f"{profile_id}: {skill_id} bar must be from 0.50 to 0.95")
        if data["status"] == "approved":
            review = profile.get("review")
            if not isinstance(review, dict) or not all(
                isinstance(review.get(key), str) and review[key].strip()
                for key in ("reviewer", "date")
            ):
                errors.append(f"{profile_id}: approved profiles require reviewer and date")
            elif not _is_iso_date(review["date"]):
                errors.append(f"{profile_id}: review date must use YYYY-MM-DD")
    if data["status"] == "approved" and not profiles:
        errors.append("an approved profile document must contain at least one profile")
    return errors


def approved_profiles(data: dict | None = None) -> list[dict]:
    data = data or load_exam_profiles()
    if data["status"] != "approved":
        return []
    return [profile for profile in data["profiles"] if profile.get("review")]


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False

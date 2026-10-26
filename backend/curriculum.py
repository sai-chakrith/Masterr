"""Versioned curriculum validation and prerequisite route construction."""
from __future__ import annotations

import json
from datetime import date
import hashlib
from pathlib import Path

CURRICULUM_PATH = Path(__file__).resolve().parents[1] / "content" / "numbers" / "curriculum.json"


class CurriculumError(ValueError):
    pass


def load_curriculum(path: Path = CURRICULUM_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurriculumError(f"Unable to load curriculum: {exc}") from exc
    problems = validate_curriculum(data)
    if problems:
        raise CurriculumError("; ".join(problems))
    return data


def validate_curriculum(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return ["curriculum must be an object"]
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        return ["skills must be a non-empty list"]
    ids = [skill.get("id") for skill in skills if isinstance(skill, dict)]
    errors = []
    if data.get("status", "draft") not in {"draft", "approved"}:
        errors.append("status must be draft or approved")
    if type(data.get("schema_version", 1)) is not int or data.get("schema_version", 1) < 1:
        errors.append("schema_version must be a positive integer")
    if len(ids) != len(skills):
        errors.append("every skill must be an object")
    if any(not isinstance(skill_id, str) or not skill_id for skill_id in ids):
        errors.append("skill IDs must be non-empty strings")
    if len(set(ids)) != len(ids):
        errors.append("skill IDs must be unique")
    known = set(ids)
    graph = {}
    for skill in skills:
        if not isinstance(skill, dict) or not isinstance(skill.get("id"), str):
            continue
        parents = skill.get("prerequisites", [])
        if not isinstance(parents, list) or any(not isinstance(p, str) for p in parents):
            errors.append(f"{skill['id']}: prerequisites must be IDs")
            continue
        if len(set(parents)) != len(parents):
            errors.append(f"{skill['id']}: duplicate prerequisite")
        for parent in set(parents) - known:
            errors.append(f"{skill['id']}: unknown prerequisite {parent}")
        graph[skill["id"]] = parents
        for example_key in ("worked_example", "half_worked_example"):
            example = skill.get(example_key)
            if example is None:
                continue
            required = ("prompt", "steps", "answer") if example_key == "worked_example" else (
                "prompt", "steps", "learner_prompt")
            if not isinstance(example, dict) or not all(key in example for key in required):
                errors.append(f"{skill['id']}: {example_key} is incomplete")
                continue
            if (not isinstance(example["prompt"], str) or not example["prompt"].strip()
                    or not isinstance(example["steps"], list) or not example["steps"]
                    or any(not isinstance(step, str) or not step.strip() for step in example["steps"])):
                errors.append(f"{skill['id']}: {example_key} needs a prompt and non-empty steps")
            if example_key == "worked_example" and (
                not isinstance(example["answer"], str) or not example["answer"].strip()
            ):
                errors.append(f"{skill['id']}: worked_example answer is required")
            if example_key == "half_worked_example" and (
                not isinstance(example["learner_prompt"], str) or not example["learner_prompt"].strip()
            ):
                errors.append(f"{skill['id']}: half_worked_example learner_prompt is required")
        if data.get("status") == "approved":
            for field in ("title", "objective", "lesson", "worked_example", "half_worked_example"):
                if not skill.get(field):
                    errors.append(f"{skill['id']}: approved curriculum requires {field}")
    visiting, visited = set(), set()

    def visit(skill_id):
        if skill_id in visiting:
            errors.append(f"prerequisite cycle includes {skill_id}")
            return
        if skill_id in visited:
            return
        visiting.add(skill_id)
        for parent in graph.get(skill_id, []):
            if parent in graph:
                visit(parent)
        visiting.remove(skill_id)
        visited.add(skill_id)

    for skill_id in graph:
        visit(skill_id)
    if data.get("status") == "approved":
        review = data.get("review")
        if not isinstance(review, dict) or not all(
            isinstance(review.get(key), str) and review[key].strip()
            for key in ("reviewer", "date")
        ):
            errors.append("approved curriculum requires reviewer and date")
        elif not _is_iso_date(review["date"]):
            errors.append("curriculum review date must use YYYY-MM-DD")
        if data.get("approval_checksum") != curriculum_digest(data):
            errors.append("approved curriculum checksum does not match its reviewed content")
    return errors


def curriculum_digest(data: dict) -> str:
    reviewed_content = {key: value for key, value in data.items()
                        if key not in {"status", "review", "approval_checksum"}}
    encoded = json.dumps(reviewed_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def skill_index(data: dict) -> dict[str, dict]:
    problems = validate_curriculum(data)
    if problems:
        raise CurriculumError("; ".join(problems))
    return {skill["id"]: skill for skill in data["skills"]}


def prerequisite_closure(targets, data: dict) -> tuple[str, ...]:
    index = skill_index(data)
    targets = tuple(dict.fromkeys(targets))
    unknown = set(targets) - index.keys()
    if not targets or unknown:
        raise CurriculumError(f"Select known target skills; unknown: {sorted(unknown)}")
    included = set()

    def include(skill_id):
        if skill_id in included:
            return
        included.add(skill_id)
        for prerequisite in index[skill_id]["prerequisites"]:
            include(prerequisite)

    for target in targets:
        include(target)
    return tuple(skill["id"] for skill in data["skills"] if skill["id"] in included)


def prerequisite_depth(data: dict) -> dict[str, int]:
    index = skill_index(data)
    memo = {}

    def depth(skill_id):
        if skill_id not in memo:
            parents = index[skill_id]["prerequisites"]
            memo[skill_id] = 0 if not parents else 1 + max(depth(p) for p in parents)
        return memo[skill_id]

    return {skill_id: depth(skill_id) for skill_id in index}

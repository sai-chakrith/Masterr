"""Pure next-action policy for explainable learner recommendations."""
from __future__ import annotations

from dataclasses import dataclass

from backend.curriculum import prerequisite_closure, prerequisite_depth, skill_index

POLICY_VERSION = "next-action-v1"
COMPLETED = {"mastered", "resolved"}


@dataclass(frozen=True)
class TopicState:
    status: str = "unassessed"
    phase: str = "none"
    score: float | None = None
    available: bool = True
    evidence_stale: bool = False


@dataclass(frozen=True)
class Action:
    kind: str
    skill_id: str | None
    reason_code: str
    reason: str


def next_actions(*, curriculum: dict, goal_targets, states, unfinished=None,
                 due_review=None, ready_to_retest=(), stuck=(), limit=3):
    if not 1 <= limit <= 3:
        raise ValueError("limit must be from one to three")
    index = skill_index(curriculum)
    route = prerequisite_closure(goal_targets, curriculum)
    depths = prerequisite_depth(curriculum)
    route_order = {skill_id: pos for pos, skill_id in enumerate(route)}

    def ordered(ids):
        return sorted(set(ids), key=lambda sid: (
            depths.get(sid, 0),
            float("inf") if states.get(sid, TopicState()).score is None else states[sid].score,
            route_order.get(sid, float("inf")),
        ))

    items = []
    if unfinished:
        items.append(unfinished)
    if due_review:
        items.append(due_review)
    for sid in ordered(s for s in ready_to_retest if s in route):
        items.append(Action("retest", sid, "practice_ready",
                            f"Your practice suggests you are ready for an independent check in {index[sid]['title']}."))
    for sid in ordered(s for s in stuck if s in route):
        parents = index[sid]["prerequisites"]
        if parents:
            parent = ordered(parents)[0]
            items.append(Action("prerequisite_check", parent, "practice_stuck",
                                f"{index[sid]['title']} builds on {index[parent]['title']}. Let's check that first."))
        else:
            items.append(Action("alternate_teaching", sid, "practice_stuck",
                                f"Practice in {index[sid]['title']} has stalled. Try a worked example."))
    for sid in route:
        state = states.get(sid, TopicState())
        if not state.available:
            continue
        if state.status == "gap":
            if state.phase in {"practice", "ready_for_retest", "tutoring_complete"}:
                items.append(Action("practice", sid, "continue_practice",
                                    f"Continue {index[sid]['title']} practice with a fresh question."))
            elif state.score is not None and state.score >= 0.50:
                items.append(Action("practice", sid, "guided_practice",
                                    f"Practise {index[sid]['title']}; ask for a hint if you need one."))
            else:
                items.append(Action("tutoring", sid, "gap_learning",
                                    f"Work on {index[sid]['title']} before checking it again."))
        elif state.status == "borderline":
            kind = "practice" if state.phase in {"practice", "tutoring_complete"} else "mistake_review"
            reason = (f"Continue practising {index[sid]['title']} with fresh questions." if kind == "practice"
                      else f"Review the answers that left {index[sid]['title']} uncertain.")
            items.append(Action(kind, sid, "borderline_review", reason))
    for sid in route:
        state = states.get(sid, TopicState())
        if state.status != "unassessed" or not state.available:
            continue
        if all(states.get(parent, TopicState()).status in COMPLETED | {"unassessed"}
               for parent in index[sid]["prerequisites"]):
            items.append(Action("diagnostic", sid, "find_starting_point",
                                f"Let's find your starting point in {index[sid]['title']}."))
    if all(states.get(sid, TopicState()).status in COMPLETED for sid in route):
        items.append(Action("route_complete", None, "route_complete",
                            "Your route is complete. Review your progress or choose another goal."))
    result, seen = [], set()
    for item in items:
        key = item.kind, item.skill_id
        if key not in seen:
            seen.add(key)
            result.append(item)
        if len(result) >= limit:
            break
    return tuple(result)

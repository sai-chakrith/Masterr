"""Compare personalised and fixed practice by the within-learner topic assignment.

    python -m scripts.personalisation_analysis --database-url sqlite:///./data/local.db \
      --out docs/personalisation-results

This reports descriptive pilot estimates. It does not decide statistical success or
claim causality; review the protocol and sample before interpreting the results.
"""
import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from math import sqrt


def normalized_gain(pre, post):
    return None if pre >= 100 else (post - pre) / (100 - pre)


def paired_strategy_effect(gains):
    """Per-learner personalised minus fixed mean gain; returns dz and paired t."""
    by_learner = defaultdict(lambda: {"personalised": [], "fixed": []})
    for row in gains:
        by_learner[row["learner"]][row["strategy"]].append(row["gain"])
    differences = [mean(values["personalised"]) - mean(values["fixed"])
                   for values in by_learner.values()
                   if values["personalised"] and values["fixed"]]
    if not differences:
        return {"learners": 0, "mean_difference": None, "dz": None, "t": None}
    average = mean(differences)
    spread = stdev(differences) if len(differences) > 1 else 0.0
    dz = average / spread if spread else None
    return {"learners": len(differences), "mean_difference": average, "dz": dz,
            "t": dz * sqrt(len(differences)) if dz is not None else None}


def load(url):
    from sqlalchemy import select
    from backend.db import make_engine, transaction
    from backend.models import (Assignment, Attempt, LearningSession,
                                RecommendationEvent, TopicPracticeConfig)

    engine = make_engine(url)
    with transaction(engine) as db:
        answer_rows = db.execute(select(Attempt, LearningSession).join(
            Assignment, Assignment.id == Attempt.assignment_id).join(
            LearningSession, LearningSession.id == Assignment.session_id)).all()
        scores_by_stage = defaultdict(list)
        practice_counts = defaultdict(lambda: {"answers": 0, "minutes": 0.0, "sessions": set()})
        for attempt, session in answer_rows:
            if session.policy_version == "validation-form-v1" and session.status == "completed":
                scores_by_stage[(attempt.learner_id, session.skill_id, session.stage)].append(attempt.correct)
            if session.policy_version in ("adaptive-practice-v1", "fixed-practice-v1"):
                bucket = practice_counts[(attempt.learner_id, session.skill_id, session.policy_version)]
                bucket["answers"] += 1
                bucket["minutes"] += (attempt.duration_ms or 0) / 60000
                bucket["sessions"].add(session.id)
        assigned = {(item.learner_id, item.skill_id): item.strategy
                    for item in db.scalars(select(TopicPracticeConfig))}
        assignment_rows = [
            {"learner": item.learner_id, "skill": item.skill_id, "strategy": item.strategy}
            for item in db.scalars(select(TopicPracticeConfig))
        ]
        recommendations = list(db.scalars(select(RecommendationEvent)))
    engine.dispose()

    stages = defaultdict(dict)
    for (learner, skill, stage), answers in scores_by_stage.items():
        stages[(learner, skill)][stage] = 100 * sum(answers) / len(answers)
    gain_rows = []
    delayed = []
    for key, values in stages.items():
        strategy = assigned.get(key)
        if strategy not in ("personalised", "fixed"):
            continue
        if "pre" in values and "post" in values:
            gain = normalized_gain(values["pre"], values["post"])
            if gain is not None:
                gain_rows.append({"learner": key[0], "skill": key[1], "strategy": strategy,
                                  "pre": values["pre"], "post": values["post"], "gain": gain})
        if "delayed" in values:
            delayed.append({"learner": key[0], "skill": key[1], "strategy": strategy,
                            "score": values["delayed"]})
    stage_presence = {key: set(values) for key, values in stages.items()}
    return gain_rows, delayed, practice_counts, recommendations, assignment_rows, stage_presence


def report(gains, delayed, practice_counts, recommendations, assignments=(), stage_presence=None):
    stage_presence = stage_presence or {}
    lines = ["# Personalised learning pilot analysis", "",
             "Descriptive analysis from saved validation forms, practice sessions and recommendation events.",
             "Interpret only after confirming the question bank, assignment roster and protocol.", "",
             "## Normalised gain by assigned practice strategy", "",
             "| Strategy | Learner-topic pairs | Mean gain |", "| --- | ---: | ---: |"]
    for strategy in ("personalised", "fixed"):
        values = [row["gain"] for row in gains if row["strategy"] == strategy]
        lines.append(f"| {strategy} | {len(values)} | {mean(values):.3f} |" if values
                     else f"| {strategy} | 0 | -- |")
    effect = paired_strategy_effect(gains)
    lines += ["", f"Paired learners: {effect['learners']}.",
              f"Mean within-learner gain difference (personalised - fixed): "
              f"{effect['mean_difference']:.3f}." if effect["mean_difference"] is not None
              else "Mean within-learner gain difference: -- (no paired data).",
              f"Paired effect size dz: {effect['dz']:.2f}." if effect["dz"] is not None
              else "Paired effect size dz: --.", "",
              "## Assignment balance and test completion", "",
              "| Strategy | Assigned pairs | Pre | Post | Delayed | Missing pre | Missing post | Missing delayed |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for strategy in ("personalised", "fixed"):
        pairs = [row for row in assignments if row["strategy"] == strategy]
        n = len(pairs)
        completed = {stage: sum(stage in stage_presence.get((row["learner"], row["skill"]), set())
                                for row in pairs)
                     for stage in ("pre", "post", "delayed")}
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            strategy, n, completed["pre"], completed["post"], completed["delayed"],
            n - completed["pre"], n - completed["post"], n - completed["delayed"]))
    topic_counts = defaultdict(lambda: {"personalised": 0, "fixed": 0})
    for row in assignments:
        topic_counts[row["skill"]][row["strategy"]] += 1
    lines.extend(["", "Per-topic assignment counts:"])
    lines.extend(f"- {skill}: personalised {counts['personalised']}, fixed {counts['fixed']}"
                 for skill, counts in sorted(topic_counts.items()))
    lines += ["", "## Delayed Form A", "", "| Strategy | Learner-topic pairs | Mean score |",
              "| --- | ---: | ---: |"]
    for strategy in ("personalised", "fixed"):
        values = [row["score"] for row in delayed if row["strategy"] == strategy]
        lines.append(f"| {strategy} | {len(values)} | {mean(values):.1f}% |" if values
                     else f"| {strategy} | 0 | -- |")
    lines += ["", "## Practice effort", "", "| Strategy | Sessions | Answers | Minutes |",
              "| --- | ---: | ---: | ---: |"]
    for strategy, policy in (("personalised", "adaptive-practice-v1"), ("fixed", "fixed-practice-v1")):
        buckets = [value for (_, _, assigned_policy), value in practice_counts.items()
                   if assigned_policy == policy]
        lines.append(f"| {strategy} | {sum(len(v['sessions']) for v in buckets)} | "
                     f"{sum(v['answers'] for v in buckets)} | {sum(v['minutes'] for v in buckets):.1f} |")
    followed = sum(event.status == "followed" for event in recommendations)
    dismissed = sum(event.status == "dismissed" for event in recommendations)
    total = len(recommendations)
    lines += ["", "## Recommendations", "",
              f"Logged suggestions: {total}; followed: {followed}; dismissed: {dismissed}.",
              f"Follow share: {followed / total:.1%}." if total else "Follow share: --.",
              "", "These estimates do not establish a learning benefit. Check missingness, "
              "assignment balance, topic difficulty and delayed-test completion before drawing conclusions."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Analyse personalised vs fixed Mastrr practice")
    parser.add_argument("--database-url", default="sqlite:///./data/local.db")
    parser.add_argument("--out", type=Path, default=Path("docs/personalisation-results"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(report(*load(args.database_url)), encoding="utf-8")
    print("wrote", args.out / "report.md")


if __name__ == "__main__":
    main()

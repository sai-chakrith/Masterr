"""K5 + S5: pilot analysis from saved answers (Stages 1-3 of the validation plan).

    python -m scripts.pilot_analysis --database-url sqlite:///./data/local.db --out docs/pilot-results

Writes report.md plus calibration.svg and learning-curves.svg into --out.

Stage 1  Does the score predict correctly? Calibration table (predicted vs actual, new
         version) and learning curves (error rate by attempt number per topic).
Stage 2  Do the labels hold up? Delayed Form A score grouped by the label the learner held.
Stage 3  Do learners learn more? Normalised gain (post - pre) / (100 - pre) per topic and
         version (Hake 1998) and the paired effect size between versions.
Also     drop-off per version, "I don't know" usage, time per topic.
"""
import argparse
from collections import defaultdict
from math import sqrt
from pathlib import Path
from statistics import mean, median, stdev

BINS = 10


# ----- pure analysis over plain rows (tested in tests/test_pilot_analysis.py) ------------------

def calibration(rows):
    """rows: dicts with predicted, correct. Returns per-bin table and weighted mean gap (points)."""
    bins = defaultdict(list)
    for r in rows:
        if r["predicted"] is not None:
            bins[min(int(r["predicted"] * BINS), BINS - 1)].append(r)
    table = []
    for b in sorted(bins):
        items = bins[b]
        table.append({"bin": f"{b / BINS:.1f}-{(b + 1) / BINS:.1f}", "n": len(items),
                      "predicted": mean(r["predicted"] for r in items),
                      "actual": mean(1.0 if r["correct"] else 0.0 for r in items)})
    total = sum(t["n"] for t in table)
    gap = sum(t["n"] * abs(t["predicted"] - t["actual"]) for t in table) / total * 100 if total else None
    return table, gap


def learning_curves(rows, max_attempts=20):
    """Error rate by attempt number (1-based) per topic, over each learner's ordered answers."""
    sequences = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["created_at"]):
        if r["source"] != "validation":
            sequences[(r["learner"], r["skill"])].append(r)
    curves = defaultdict(lambda: defaultdict(list))
    for (_, skill), answers in sequences.items():
        for i, r in enumerate(answers[:max_attempts], start=1):
            curves[skill][i].append(0.0 if r["correct"] else 1.0)
    return {skill: [(i, mean(v), len(v)) for i, v in sorted(points.items())]
            for skill, points in curves.items()}


def validation_scores(rows):
    """{(learner, skill): {stage: percent correct}} from completed validation forms."""
    grouped = defaultdict(list)
    for r in rows:
        if r["source"] == "validation" and r["session_status"] == "completed":
            grouped[(r["learner"], r["skill"], r["stage"])].append(r["correct"])
    scores = defaultdict(dict)
    for (learner, skill, stage), answers in grouped.items():
        scores[(learner, skill)][stage] = 100.0 * sum(answers) / len(answers)
    return scores


def normalised_gain(pre, post):
    return None if pre >= 100 else (post - pre) / (100 - pre)


def gains(scores, versions):
    """Per (learner, skill) gain with the topic's version. versions: {(learner, skill): version}."""
    out = []
    for key, stages in scores.items():
        if "pre" in stages and "post" in stages:
            g = normalised_gain(stages["pre"], stages["post"])
            if g is not None:
                out.append({"learner": key[0], "skill": key[1], "version": versions.get(key, "current"),
                            "pre": stages["pre"], "post": stages["post"], "gain": g})
    return out


def paired_effect(gain_rows):
    """Within-learner difference of mean gain (new - current); Cohen's dz and paired t."""
    per = defaultdict(lambda: {"new": [], "current": []})
    for g in gain_rows:
        per[g["learner"]][g["version"]].append(g["gain"])
    diffs = [mean(v["new"]) - mean(v["current"]) for v in per.values() if v["new"] and v["current"]]
    if len(diffs) < 2:
        return {"learners": len(diffs), "mean_difference": mean(diffs) if diffs else None, "dz": None, "t": None}
    sd = stdev(diffs)
    dz = mean(diffs) / sd if sd else None
    return {"learners": len(diffs), "mean_difference": mean(diffs), "dz": dz,
            "t": dz * sqrt(len(diffs)) if dz is not None else None}


def label_outcomes(scores, labels):
    """Stage 2: delayed score grouped by label. labels: {(learner, skill): status}."""
    grouped = defaultdict(list)
    for key, stages in scores.items():
        if "delayed" in stages:
            grouped[labels.get(key, "unassessed")].append(stages["delayed"])
    return {label: {"n": len(v), "mean": mean(v)} for label, v in sorted(grouped.items())}


def tracking(rows, sessions):
    """Drop-off, "I don't know" usage and time per topic, by version."""
    out = {}
    for version in ("current", "new"):
        mine = [s for s in sessions if s["version"] == version and s["policy"] != "validation-form-v1"]
        answers = [r for r in rows if r["version"] == version and r["source"] != "validation"]
        times = defaultdict(int)
        for r in answers:
            times[(r["learner"], r["skill"])] += r["duration_ms"] or 0
        out[version] = {
            "sessions": len(mine),
            "abandoned": sum(s["status"] == "abandoned" for s in mine),
            "answers": len(answers),
            "dont_know_rate": mean(1.0 if r["dont_know"] else 0.0 for r in answers) if answers else None,
            "median_minutes_per_topic": median(t / 60000 for t in times.values()) if times else None,
        }
    return out


# ----- charts (plain SVG, no plotting dependency) -----------------------------------------------

def svg_calibration(table):
    size, pad = 360, 40
    span = size - 2 * pad

    def xy(p, a):
        return pad + p * span, size - pad - a * span
    points = "".join(
        f'<circle cx="{xy(t["predicted"], t["actual"])[0]:.1f}" cy="{xy(t["predicted"], t["actual"])[1]:.1f}" '
        f'r="{3 + min(t["n"], 400) ** 0.5 / 3:.1f}" fill="#2563eb" fill-opacity="0.7"/>' for t in table)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" font-family="sans-serif" font-size="11">'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<line x1="{pad}" y1="{size - pad}" x2="{size - pad}" y2="{pad}" stroke="#9ca3af" stroke-dasharray="4"/>'
            f'<line x1="{pad}" y1="{size - pad}" x2="{size - pad}" y2="{size - pad}" stroke="black"/>'
            f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{size - pad}" stroke="black"/>'
            f'<text x="{size / 2}" y="{size - 8}" text-anchor="middle">Predicted chance right</text>'
            f'<text x="12" y="{size / 2}" transform="rotate(-90 12 {size / 2})" text-anchor="middle">Actual share right</text>'
            f'{points}</svg>')


def svg_curves(curves):
    width, height, pad = 520, 320, 44
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"]
    longest = max((len(c) for c in curves.values()), default=1) or 1
    lines, legend = [], []
    for i, (skill, points) in enumerate(sorted(curves.items())):
        color = colors[i % len(colors)]
        path = " ".join(f"{pad + (n - 1) / max(longest - 1, 1) * (width - 2 * pad):.1f},"
                        f"{height - pad - err * (height - 2 * pad):.1f}" for n, err, _ in points)
        lines.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2"/>')
        legend.append(f'<text x="{width - pad}" y="{pad + 14 * i}" text-anchor="end" fill="{color}">{skill}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif" font-size="11">'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="black"/>'
            f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="black"/>'
            f'<text x="{width / 2}" y="{height - 10}" text-anchor="middle">Attempt number on the topic</text>'
            f'<text x="12" y="{height / 2}" transform="rotate(-90 12 {height / 2})" text-anchor="middle">Error rate</text>'
            + "".join(lines) + "".join(legend) + "</svg>")


# ----- database loading and report ------------------------------------------------------------------

def load(url):
    from sqlalchemy import select

    from backend.db import make_engine, transaction
    from backend.models import Assignment, Attempt, GapState, LearningSession, Question

    engine = make_engine(url)
    with transaction(engine) as db:
        answer_rows = db.execute(
            select(Attempt, LearningSession, Question.difficulty_level)
            .join(Assignment, Assignment.id == Attempt.assignment_id)
            .join(LearningSession, LearningSession.id == Assignment.session_id)
            .join(Question, Question.id == Assignment.question_id)).all()
        rows = [{"learner": a.learner_id, "skill": s.skill_id, "version": a.scoring_version, "source": a.source,
                 "stage": s.stage, "session_status": s.status, "created_at": a.created_at,
                 "correct": a.correct, "dont_know": a.dont_know, "predicted": a.predicted_probability,
                 "duration_ms": a.duration_ms, "level": level, "assistance": a.assistance}
                for a, s, level in answer_rows]
        sessions = [{"version": s.scoring_version, "policy": s.policy_version, "status": s.status}
                    for s in db.scalars(select(LearningSession))]
        labels = {(g.learner_id, g.skill_id): g.status for g in db.scalars(select(GapState))}
        versions = {(s.learner_id, s.skill_id): s.scoring_version
                    for s in db.scalars(select(LearningSession).where(
                        LearningSession.policy_version != "validation-form-v1"))}
    engine.dispose()
    return rows, sessions, labels, versions


def fmt(value, spec=".1f", suffix=""):
    return "--" if value is None else f"{value:{spec}}{suffix}"


def report(rows, sessions, labels, versions):
    independent_new = [r for r in rows if r["version"] == "new" and r["assistance"] == "independent"]
    table, gap = calibration(independent_new)
    curves = learning_curves([r for r in rows if r["assistance"] == "independent"])
    scores = validation_scores(rows)
    gain_rows = gains(scores, versions)
    effect = paired_effect(gain_rows)
    lines = ["# Pilot results", "", "Generated by scripts/pilot_analysis.py from saved answers.", "",
             "## Stage 1: does the score predict correctly?", "",
             f"Weighted gap between predicted and actual: {fmt(gap)} points (pass: about 5 or less).", "",
             "![Calibration](calibration.svg)", "",
             "| Predicted bin | Answers | Mean predicted | Actual |", "| --- | --- | --- | --- |"]
    lines += [f"| {t['bin']} | {t['n']} | {t['predicted']:.2f} | {t['actual']:.2f} |" for t in table]
    lines += ["", "Learning curves should fall smoothly; a flat or bumpy curve means the topic mixes skills.", "",
              "![Learning curves](learning-curves.svg)", "",
              "## Stage 2: do the labels hold up?", "",
              "Delayed Form A score by label (pass: Mastered and Resolved about 75%+, Gap clearly lower).", "",
              "| Label | Learners | Mean delayed score |", "| --- | --- | --- |"]
    lines += [f"| {k} | {v['n']} | {v['mean']:.1f}% |" for k, v in label_outcomes(scores, labels).items()]
    lines += ["", "## Stage 3: do learners learn more?", "",
              "| Version | Topics | Mean normalised gain |", "| --- | --- | --- |"]
    for version in ("current", "new"):
        mine = [g["gain"] for g in gain_rows if g["version"] == version]
        lines.append(f"| {version} | {len(mine)} | {fmt(mean(mine) if mine else None, '.3f')} |")
    lines += ["", f"Paired learners: {effect['learners']}. Mean difference (new - current): "
              f"{fmt(effect['mean_difference'], '.3f')}. Effect size dz: {fmt(effect['dz'], '.2f')}. "
              f"Paired t: {fmt(effect['t'], '.2f')}. Pass: dz between 0.3 and 0.5 or above.", "",
              "## Tracking", "", "| Measure | Current | New |", "| --- | --- | --- |"]
    track = tracking(rows, sessions)
    for key, label in (("sessions", "Sessions started"), ("abandoned", "Sessions abandoned"),
                       ("answers", "Answers"), ("dont_know_rate", "\"I don't know\" share"),
                       ("median_minutes_per_topic", "Median minutes per topic")):
        c, n = track["current"][key], track["new"][key]
        spec = ".2f" if isinstance(c, float) or isinstance(n, float) else "d"
        lines.append(f"| {label} | {fmt(c, spec)} | {fmt(n, spec)} |")
    lines += ["", "Reading the results: Stage 1 fails, fix tags or scoring first. Stage 2 fails, cut-offs or",
              "retest are too loose. Stages 1-2 pass but Stage 3 does not, measurement is fine and tutoring",
              "is the problem. The survey answers live in the pilot sheet, not in this database."]
    return "\n".join(lines) + "\n", svg_calibration(table), svg_curves(curves)


def main():
    parser = argparse.ArgumentParser(description="Mastrr pilot analysis (Stages 1-3)")
    parser.add_argument("--database-url", default="sqlite:///./data/local.db")
    parser.add_argument("--out", type=Path, default=Path("docs/pilot-results"))
    args = parser.parse_args()
    text, calibration_svg, curves_svg = report(*load(args.database_url))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(text, encoding="utf-8")
    (args.out / "calibration.svg").write_text(calibration_svg, encoding="utf-8")
    (args.out / "learning-curves.svg").write_text(curves_svg, encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()

"""K2: simulated learners for the current and new scoring designs.

Runs the real engine in backend/mastery.py, so a rule change there is tested here.
Re-run after every rule change and commit the regenerated report:

    .venv/Scripts/python.exe -m scripts.convergence_study --markdown docs/simulation-results.md

Assumptions (sizes, not promises; real learners are messier):
- True skill theta is in rating units; above the bar means theta >= ln 3 (knows 75% of level 3).
- A learner knows a question with chance sigmoid(theta - difficulty). Otherwise they press
  "I don't know" with chance idk_rate (new design only) or guess one of 4 options.
- Current design: 6 questions from an even bank, Mastered when more than half are right;
  retest = the 3 easiest questions, passed at 2/3, no "I don't know" button.
- New design: D4 diagnostic (8-12, alternating 3/4, re-scored), D6 retest (10 unseen,
  levels 3-4 then nearest, 7/10), mid-weighted bank 3/6/11/11/4 with 1/2/3/3/1 hidden.
- Gap learners are tutored (skill rises by a uniform random gain); Borderline learners only
  review missed questions (small gain). Everyone not Mastered then takes the retest.
"""
import argparse
import random
from dataclasses import dataclass, replace
from math import log
from pathlib import Path

from backend import mastery as m

BAR_THETA = log(3)
OPTIONS = 4
SPLITS = {"mid": (3, 6, 11, 11, 4), "even": (7, 7, 7, 7, 7)}
HIDDEN = (1, 2, 3, 3, 1)


@dataclass(frozen=True)
class Config:
    learners: int = 8000
    pop_sd: float = 1.3
    idk_rate: float = 0.6
    tutoring_gain: float = 1.6
    review_gain: float = 0.3
    bank: str = "mid"
    prior_sd: float = m.PRIOR_SD
    mastered_line: float = m.MASTERED_LINE
    gap_line: float = m.GAP_LINE
    retest_pass: int = m.RETEST_PASS
    seed: int = 7


def answer(rng, theta, level, idk_allowed, idk_rate):
    if rng.random() < m.sigmoid(theta - m.difficulty(level)):
        return m.RIGHT
    if idk_allowed and rng.random() < idk_rate:
        return m.DONT_KNOW
    return m.RIGHT if rng.random() < 1 / OPTIONS else m.WRONG


def visible_bank(bank):
    return {level: count - hidden for level, count, hidden in zip(range(1, 6), SPLITS[bank], HIDDEN)}


def take(pool, target):
    """Pick from the target level, else the nearest level with questions left (K4)."""
    for level in sorted(pool, key=lambda lv: (abs(lv - target), lv)):
        if pool[level] > 0:
            pool[level] -= 1
            return level
    raise RuntimeError("bank exhausted")


def take_retest(pool):
    """Levels 3-4 first, then the nearest tagged level (same order as the API, S1)."""
    levels = []
    for _ in range(m.RETEST_SIZE):
        level = min((lv for lv in pool if pool[lv] > 0),
                    key=lambda lv: (min(abs(lv - 3), abs(lv - 4)), lv))
        pool[level] -= 1
        levels.append(level)
    return levels


def new_diagnostic(rng, theta, pool, cfg):
    answers = []
    while True:
        level = take(pool, m.diagnostic_level(len(answers)))
        answers.append((level, answer(rng, theta, level, True, cfg.idk_rate)))
        decision = m.decide(answers, cfg.prior_sd, cfg.mastered_line, cfg.gap_line)
        if decision.status != "continue":
            return decision.status


def new_retest(rng, theta, pool, cfg):
    levels = take_retest(pool)
    fallback = sum(lv not in (3, 4) for lv in levels)
    right = sum(answer(rng, theta, lv, True, cfg.idk_rate) == m.RIGHT for lv in levels)
    return right >= cfg.retest_pass, fallback


def current_diagnostic(rng, theta):
    right = sum(answer(rng, theta, rng.randint(1, 5), False, 0) == m.RIGHT for _ in range(6))
    return "mastered" if right / 6 > 0.5 else "gap"


def current_retest(rng, theta):
    return sum(answer(rng, theta, 1, False, 0) == m.RIGHT for _ in range(3)) >= 2


def run(cfg):
    rng = random.Random(cfg.seed)
    t = dict.fromkeys(("below", "above", "cur_below_m", "cur_above_m", "new_below_m", "new_above_m",
                       "new_above_gap", "new_border", "weak", "improved", "cur_weak_pass",
                       "cur_improved_fail", "new_weak_pass", "new_improved_fail", "fallback", "retests"), 0)
    for _ in range(cfg.learners):
        theta = rng.gauss(BAR_THETA, cfg.pop_sd)
        above = theta >= BAR_THETA
        t["above" if above else "below"] += 1
        if current_diagnostic(rng, theta) == "mastered":
            t["cur_above_m" if above else "cur_below_m"] += 1
        pool = visible_bank(cfg.bank)
        new = new_diagnostic(rng, theta, pool, cfg)
        if new == "mastered":
            t["new_above_m" if above else "new_below_m"] += 1
            continue
        if new == "borderline":
            t["new_border"] += 1
        elif above:
            t["new_above_gap"] += 1
        # Both designs retest the same post-tutoring learner.
        gain = rng.uniform(0, cfg.tutoring_gain if new == "gap" else cfg.review_gain)
        after = theta + gain
        weak = after < BAR_THETA
        t["weak" if weak else "improved"] += 1
        passed, fallback = new_retest(rng, after, pool, cfg)
        t["fallback"] += fallback
        t["retests"] += 1
        cur_passed = current_retest(rng, after)
        if weak:
            t["new_weak_pass"] += passed
            t["cur_weak_pass"] += cur_passed
        else:
            t["new_improved_fail"] += not passed
            t["cur_improved_fail"] += not cur_passed

    def pct(n, d):
        return 100 * n / d if d else float("nan")
    return {
        "Below-bar learners marked Mastered at diagnostic": (pct(t["cur_below_m"], t["below"]), pct(t["new_below_m"], t["below"])),
        "Above-bar learners marked Mastered at diagnostic": (pct(t["cur_above_m"], t["above"]), pct(t["new_above_m"], t["above"])),
        "Above-bar learners marked Gap at diagnostic": (None, pct(t["new_above_gap"], t["above"])),
        "Learners sent to the Borderline path": (0.0, pct(t["new_border"], cfg.learners)),
        "Still-weak learners passing the retest": (pct(t["cur_weak_pass"], t["weak"]), pct(t["new_weak_pass"], t["weak"])),
        "Truly improved learners failing the retest": (pct(t["cur_improved_fail"], t["improved"]), pct(t["new_improved_fail"], t["improved"])),
        "Retest questions off levels 3-4 (of 10)": (None, t["fallback"] / max(t["retests"], 1)),
    }


def curve(cfg, per_level=4000, points=(0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95)):
    """Chance of a Mastered label by true skill (the proposal's chart)."""
    rng = random.Random(cfg.seed + 1)
    rows = []
    for score in points:
        theta = m.rating_for(score)
        cur = sum(current_diagnostic(rng, theta) == "mastered" for _ in range(per_level))
        new = sum(new_diagnostic(rng, theta, visible_bank(cfg.bank), cfg) == "mastered" for _ in range(per_level))
        rows.append((score, 100 * cur / per_level, 100 * new / per_level))
    return rows


PROPOSAL = ["40.1% / 2.2%", "88.9% / 45.7%", "-- / 1.7%", "0% / 43%", "95.4% / 18.9%", "0.1% / 14.9%", "-- / 4"]
SWEEPS = (
    ("Baseline", {}),
    ("Mastered line 85%", {"mastered_line": 0.85}),
    ("Even bank, 7 per level", {"bank": "even"}),
    ("Retest 6/10", {"retest_pass": 6}),
    ("Retest 8/10", {"retest_pass": 8}),
    ("\"I don't know\" used 30%", {"idk_rate": 0.3}),
    ("Prior sd 1.0", {"prior_sd": 1.0}),
    ("Prior sd 2.5", {"prior_sd": 2.5}),
)


def fmt(v):
    return "--" if v is None else f"{v:.1f}%"


def to_markdown(cfg, results, rows, sweeps):
    lines = [
        "# K2 simulation results", "",
        "Generated by scripts/convergence_study.py from the engine in backend/mastery.py.",
        "All numbers come from simulated learners. Re-run after every rule change.", "",
        "## Setup", "",
        f"- {cfg.learners} learners, true skill normal around the bar (sd {cfg.pop_sd} logits), seed {cfg.seed}.",
        f"- Unknown questions: \"I don't know\" {cfg.idk_rate:.0%} of the time, otherwise a 1-in-4 guess.",
        f"- Gap learners gain uniform 0-{cfg.tutoring_gain} logits from tutoring; Borderline 0-{cfg.review_gain} from review.",
        f"- Bank split {SPLITS[cfg.bank]} with hidden {HIDDEN}; re-score prior sd {cfg.prior_sd}.",
        f"- Cut-offs: Mastered {cfg.mastered_line:.0%}, Gap below {cfg.gap_line:.0%}, retest {cfg.retest_pass}/10.",
        "- Current design is modelled from the proposal's description (6 questions, more than half right;",
        "  3 easiest retest at 2/3); the original _score() code is not in this repository.", "",
        "## Expected impact", "",
        "| Measure | Current | New | Proposal (current / new) |", "| --- | --- | --- | --- |"]
    for (name, (cur, new)), ref in zip(results.items(), PROPOSAL):
        new_text = f"{new:.1f}" if "of 10" in name else fmt(new)
        lines.append(f"| {name} | {fmt(cur)} | {new_text} | {ref} |")
    lines += ["", "## Chance of a Mastered label by true skill", "",
              "True skill = share of typical (level-3) questions the learner knows. The bar is 75%.", "",
              "| True skill | Current | New |", "| --- | --- | --- |"]
    lines += [f"| {s:.0%} | {c:.1f}% | {n:.1f}% |" for s, c, n in rows]
    lines += ["", "## Sensitivity", "",
              "| Variant | Below-bar Mastered | Above-bar Mastered | Borderline | Still-weak pass | Improved fail |",
              "| --- | --- | --- | --- | --- | --- |"]
    for name, res in sweeps:
        keys = list(res)
        lines.append(f"| {name} | " + " | ".join(fmt(res[keys[i]][1]) for i in (0, 1, 3, 4, 5)) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="K2 scoring simulation")
    parser.add_argument("--learners", type=int, default=Config.learners)
    parser.add_argument("--prior-sd", type=float, default=Config.prior_sd)
    parser.add_argument("--pop-sd", type=float, default=Config.pop_sd)
    parser.add_argument("--tutoring-gain", type=float, default=Config.tutoring_gain)
    parser.add_argument("--seed", type=int, default=Config.seed)
    parser.add_argument("--markdown", type=Path, help="write the full report with curve and sensitivity")
    args = parser.parse_args()
    cfg = Config(learners=args.learners, prior_sd=args.prior_sd, pop_sd=args.pop_sd,
                 tutoring_gain=args.tutoring_gain, seed=args.seed)
    results = run(cfg)
    for name, (cur, new) in results.items():
        print(f"{name:52} current {fmt(cur):>7}  new {new:6.1f}")
    if args.markdown:
        sweeps = [(label, run(replace(cfg, **change))) for label, change in SWEEPS]
        args.markdown.write_text(to_markdown(cfg, results, curve(cfg), sweeps), encoding="utf-8")
        print("wrote", args.markdown)


if __name__ == "__main__":
    main()

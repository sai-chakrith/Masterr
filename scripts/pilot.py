"""C5 pilot accounts and the per-learner, per-topic version switch (D8).

    python -m scripts.pilot assign learner-ids.txt --seed 2026 --out data/pilot-assignments.csv
    python -m scripts.pilot flip <learner-id> <skill-id> new|current
    python -m scripts.pilot show <learner-id>

learner-ids.txt holds one authenticated subject per line (the Supabase user id of each
pilot account). Each learner gets the new design on half of the topics, chosen at random
per learner, and the current design on the rest. Assign before learners start a topic:
sessions keep the version they started with, so a later flip affects only new sessions.
"""
import argparse
import csv
import os
import random
import sys
from pathlib import Path

from backend.db import make_engine
from backend.learning import CURRICULUM, LearningService

SKILL_IDS = [s["id"] for s in CURRICULUM]
PILOT_SKILL_IDS = [
    "integer-properties", "percentages", "profit-loss", "simple-interest",
    "compound-interest", "ratio-proportion", "averages", "mixtures-alligations",
    "partnership", "time-work",
]


def split_topics(learner, seed, skills=SKILL_IDS):
    """Random half of the topics get the new design; stable for a given learner and seed."""
    rng = random.Random(f"{seed}:{learner}")
    chosen = set(rng.sample(list(skills), len(skills) // 2))
    return {skill: "new" if skill in chosen else "current" for skill in skills}


def split_practice_topics(learner, seed, skills=SKILL_IDS):
    """Stable within-learner practice strategy split, independent of score version."""
    rng = random.Random(f"practice:{seed}:{learner}")
    chosen = set(rng.sample(list(skills), len(skills) // 2))
    return {skill: "personalised" if skill in chosen else "fixed" for skill in skills}


def service(url):
    return LearningService(make_engine(url))


def cmd_assign(args):
    learners = [line.strip() for line in Path(args.learners).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")]
    if len(set(learners)) != len(learners):
        raise SystemExit("Duplicate learner ids in the list")
    svc = service(args.database_url)
    rows = []
    for learner in learners:
        svc.register(learner)
        for skill, version in split_topics(learner, args.seed).items():
            svc.set_scoring_version(learner, skill, version)
            rows.append({"learner_id": learner, "skill_id": skill, "scoring_version": version})
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, ["learner_id", "skill_id", "scoring_version"])
            writer.writeheader()
            writer.writerows(rows)
        print("wrote", args.out)
    print(f"Assigned {len(learners)} learners across {len(SKILL_IDS)} topics")
    return 0


def cmd_flip(args):
    svc = service(args.database_url)
    svc.register(args.learner)
    print(svc.set_scoring_version(args.learner, args.skill, args.version))
    return 0


def cmd_show(args):
    for row in service(args.database_url).gaps(args.learner):
        print(f"{row['skill_id']:20} {row['scoring_version']:8} {row['status']:11} "
              f"score={row['score']} answers={row['answer_count']}")
    return 0


def cmd_assign_practice(args):
    learners = [line.strip() for line in Path(args.learners).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")]
    if len(set(learners)) != len(learners):
        raise SystemExit("Duplicate learner ids in the list")
    skills = args.skills or PILOT_SKILL_IDS
    unknown = set(skills) - set(SKILL_IDS)
    if unknown:
        raise SystemExit(f"Unknown skill ids: {', '.join(sorted(unknown))}")
    if len(skills) < 2 or len(set(skills)) != len(skills):
        raise SystemExit("Choose at least two distinct skills")
    svc = service(args.database_url)
    rows = []
    for learner in learners:
        svc.register(learner)
        for skill, strategy in split_practice_topics(learner, args.seed, skills).items():
            svc.set_practice_strategy(learner, skill, strategy)
            svc.set_scoring_version(learner, skill, args.scoring_version)
            rows.append({"learner_id": learner, "skill_id": skill, "practice_strategy": strategy,
                         "scoring_version": args.scoring_version})
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, ["learner_id", "skill_id", "practice_strategy", "scoring_version"])
            writer.writeheader()
            writer.writerows(rows)
        print("wrote", args.out)
    print(f"Assigned practice strategies for {len(learners)} learners across {len(skills)} topics")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mastrr pilot version switch")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", "sqlite:///./data/local.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("assign")
    p.add_argument("learners")
    p.add_argument("--seed", default="mastrr-pilot")
    p.add_argument("--out")
    p.set_defaults(run=cmd_assign)
    p = sub.add_parser("flip")
    p.add_argument("learner")
    p.add_argument("skill", choices=SKILL_IDS)
    p.add_argument("version", choices=("new", "current"))
    p.set_defaults(run=cmd_flip)
    p = sub.add_parser("show")
    p.add_argument("learner")
    p.set_defaults(run=cmd_show)
    p = sub.add_parser("assign-practice")
    p.add_argument("learners")
    p.add_argument("--skills", nargs="+", choices=SKILL_IDS)
    p.add_argument("--seed", default="mastrr-personalised-pilot")
    p.add_argument("--scoring-version", choices=("new", "current"), default="new")
    p.add_argument("--out")
    p.set_defaults(run=cmd_assign_practice)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

"""Compare personal tutoring on authorised, completed visible mistakes.

Manual operator tool: sends selected data to Groq, writes only aggregate metrics.
Never reads hidden validation items or changes the configured production model.
"""
import argparse
import json
import os
import time
from dataclasses import replace

from backend.db import make_engine
from backend.tutor import TutorService, TutorSettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic")
    parser.add_argument("--learner", action="append", required=True)
    parser.add_argument("--confirm-authorized", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    settings = TutorSettings.from_env()
    if not args.confirm_authorized or not settings.api_key:
        parser.error("Requires --confirm-authorized for these learner records and a GROQ_API_KEY.")
    if not 1 <= args.limit <= 100:
        parser.error("Limit must be between 1 and 100.")
    engine = make_engine(os.environ.get("DATABASE_URL", "sqlite:///./data/local.db"))
    try:
        source = TutorService(engine, settings)
        notes = source.notes(args.topic)
        if not notes:
            parser.error("Publish reviewed notes before comparing models.")
        cases, seen = [], set()
        for learner in args.learner:
            for item in source._context(learner, args.topic):
                key = (item["question_id"], item["learner_answer"])
                if key not in seen:
                    seen.add(key)
                    cases.append(item)
        cases = cases[:args.limit]
        if not cases:
            parser.error("No eligible completed mistakes are available.")
        for model in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            tutor = TutorService(engine, replace(settings, model=model))
            usage, checked, durations = [], 0, []
            for case in cases:
                start = time.monotonic()
                result = tutor._personal(notes, [case], usage)
                durations.append(round((time.monotonic() - start) * 1000))
                checked += int(result["answer_checked"])
            def total(field):
                values = [row.get(field) for row in usage]
                return sum(values) if values and all(isinstance(v, int) for v in values) else None
            print(json.dumps({"model": model, "cases": len(cases), "answer_checked": checked,
                              "answer_checked_rate": checked/len(cases), "duration_ms": durations,
                              "prompt_tokens": total("prompt_tokens"), "completion_tokens": total("completion_tokens"),
                              "reasoning_tokens": total("reasoning_tokens"), "usage": usage,
                              "limitation": "Final-answer check only; human review of working remains required."}, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

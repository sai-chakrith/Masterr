"""Idempotently import the original drafts; no automatic publication."""
import os

from backend.content import import_questions
from backend.db import make_engine, transaction
from backend.numbers.bank import load_questions


def main():
    engine = make_engine(os.environ.get("DATABASE_URL", "sqlite:///./data/local.db"))
    with transaction(engine) as db:
        count = import_questions(db, load_questions())
    print(f"Imported {count} question versions. Draft status is preserved.")


if __name__ == "__main__":
    main()

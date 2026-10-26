"""Start a guarded loopback API with a NEW synthetic browser-test database."""
import copy
import os
import tempfile
from pathlib import Path
from alembic import command
from alembic.config import Config
import uvicorn
from backend.content import import_questions
from backend.db import make_engine, transaction
from backend.learning import LearningService
from backend.numbers.bank import load_questions
from backend.review import ReviewService
from tests.test_scoring_flow import full_bank


def main():
    if os.environ.get("MASTRR_E2E") != "1" or os.environ.get("LOCAL_DEVELOPMENT") != "1":
        raise SystemExit("This synthetic fixture server requires MASTRR_E2E=1 and LOCAL_DEVELOPMENT=1.")
    root = Path(__file__).resolve().parents[1]
    folder = root / ".e2e"
    folder.mkdir(exist_ok=True)
    handle, filename = tempfile.mkstemp(prefix="synthetic-", suffix=".db", dir=folder)
    os.close(handle)
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(filename).resolve())
    os.environ["GROQ_API_KEY"] = ""  # Browser tests must never make a paid provider call.
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    engine = make_engine(os.environ["DATABASE_URL"])
    bank = full_bank()
    seed = next(q for q in load_questions() if q["id"] == "num-003")
    for i in range(89):
        q = copy.deepcopy(seed)
        q.update(id=f"e2e-practice-{i:03}", family_id=f"e2e-practice-family-{i:03}", purpose="practice",
                 difficulty_level=(i % 5) + 1, review_status="approved",
                 review={"reviewer": "SYNTHETIC_E2E_ONLY", "date": "2026-10-27"},
                 provenance="SYNTHETIC_E2E_ONLY_NOT_HUMAN_APPROVED")
        if i >= 80:
            q["purpose"] = "review"
            q["facet"] = ("basic", "combined", "constraints")[(i - 80) % 3]
        bank.append(q)
    with transaction(engine) as db:
        import_questions(db, bank)
    learning = LearningService(engine)
    learning.register("local-developer")
    learning.set_scoring_version("local-developer", "divisibility", "new")
    reviews = ReviewService(engine)
    for key in ("curriculum", "notes:divisibility"):
        old = reviews.document(key)
        reviews.review_document(key, "SYNTHETIC_E2E_ONLY", "approve", old["checksum"])
    engine.dispose()
    print("Synthetic browser-test fixture only. A new isolated database was created.", flush=True)
    uvicorn.run("backend.api:create_app", factory=True, host="127.0.0.1", port=8765, access_log=False)


if __name__ == "__main__":
    main()

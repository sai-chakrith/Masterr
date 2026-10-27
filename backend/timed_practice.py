"""Timed practice uses visible practice items and never updates diagnostic/mastery state."""
from datetime import datetime, timedelta, timezone
from random import SystemRandom
from uuid import uuid4
from sqlalchemy import select
from backend.app_models import TimedTest, TestExposure
from backend.content import available_questions, is_current_question
from backend.db import transaction
from backend.learning import LearningError, LearningService, normalized_integer
from backend.mock_state import active_test
from backend.models import Question
from backend.numbers.bank import compute_answer, load_curriculum


class TimedPracticeService:
    def __init__(self, engine, learning=None, clock=None):
        self.engine, self.learning = engine, learning or LearningService(engine)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def start(self, owner, skills, count, minutes):
        known = {s["id"] for s in load_curriculum()["skills"]}
        if not skills or len(set(skills)) != len(skills) or set(skills) - known:
            raise LearningError("invalid_topics", "Choose distinct topics from the current curriculum.", 422)
        if not 3 <= count <= 30 or not 1 <= minutes <= 120 or count < len(skills):
            raise LearningError("invalid_test", "Choose 3–30 questions and 1–120 minutes.", 422)
        with transaction(self.engine) as db:
            self.learning.lock_learner(db, owner)
            if self.learning.active_session(db, owner) or active_test(db, owner):
                raise LearningError("active_session", "Finish or abandon your current activity first.")
            seen = self.learning.seen_families(db, owner)
            pools = [[q for q in available_questions(db, s, "practice") if q.family_id not in seen] for s in skills]
            for pool in pools:
                SystemRandom().shuffle(pool)
            # Match each requested topic to a distinct family before filling
            # remaining slots. Augmenting paths handle overlapping families.
            matched = {}
            def cover(topic, visited):
                for q in pools[topic]:
                    if q.family_id in visited:
                        continue
                    visited.add(q.family_id)
                    previous = matched.get(q.family_id)
                    if previous is None or cover(previous[0], visited):
                        matched[q.family_id] = (topic, q)
                        return True
                return False
            if not all(cover(i, set()) for i in range(len(pools))):
                raise LearningError("insufficient_coverage", "Every selected topic needs a fresh reviewed question. Choose other topics.")
            chosen = [q for _, q in sorted(matched.values(), key=lambda item: item[0])]
            seen.update(q.family_id for q in chosen)
            # Round-robin topics so one large bank does not dominate a mixed test.
            while len(chosen) < count and any(pools):
                for pool in pools:
                    while pool and pool[-1].family_id in seen:
                        pool.pop()
                    if pool and len(chosen) < count:
                        q = pool.pop(); chosen.append(q); seen.add(q.family_id)
            if len(chosen) < count:
                raise LearningError("insufficient_coverage", "Not enough fresh reviewed practice questions. Choose fewer questions or another topic.")
            run = TimedTest(id=str(uuid4()), learner_id=owner, skill_ids=skills,
                question_ids=[q.id for q in chosen], answers={}, status="active", created_at=self.clock().isoformat(),
                deadline=(self.clock() + timedelta(minutes=minutes)).isoformat())
            db.add(run); db.flush()
            for q in chosen:
                db.add(TestExposure(id=str(uuid4()), learner_id=owner, test_id=run.id, family_id=q.family_id))
            return {"id": run.id}

    def owned(self, db, owner, run_id):
        row = db.get(TimedTest, run_id)
        if not row or row.learner_id != owner:
            raise LearningError("not_found", "Timed practice not found.", 404)
        if row.status == "active" and self.clock().isoformat() >= row.deadline:
            row.status, row.finished_at = "completed", self.clock().isoformat()
        return row

    def view(self, db, row):
        answered = len(row.answers)
        qid = next((q for q in row.question_ids if q not in row.answers), None)
        question = None
        if row.status == "active" and qid:
            q = db.get(Question, qid)
            if not is_current_question(db, q):
                raise LearningError("content_unavailable", "A question was changed or withdrawn. End this test and choose fresh content.")
            question = {"id": q.id, "prompt": q.snapshot["prompt"], "skill_id": q.skill_id,
                        "options": [{"id": o["id"], "text": o["text"]} for o in q.snapshot.get("options", [])]}
        result = {"id": row.id, "status": row.status, "skill_ids": row.skill_ids,
                  "question_count": len(row.question_ids), "answered": answered,
                  "deadline": row.deadline, "server_time": self.clock().isoformat(), "question": question}
        if row.status != "active":
            result["correct"] = sum(a["correct"] for a in row.answers.values())
            result["outcomes"] = [{"question": db.get(Question, q).snapshot["prompt"],
                "skill_id": db.get(Question, q).skill_id, "answered": q in row.answers,
                "correct": row.answers.get(q, {}).get("correct", False),
                "solution": db.get(Question, q).snapshot["solution"] if is_current_question(db, db.get(Question, q)) else "Content changed; the previous explanation is withheld."}
                for q in row.question_ids]
        return result

    def get(self, owner, run_id):
        with transaction(self.engine) as db:
            self.learning.lock_learner(db, owner)
            return self.view(db, self.owned(db, owner, run_id))

    def answer(self, owner, run_id, qid, answer, option_id, dont_know):
        with transaction(self.engine) as db:
            self.learning.lock_learner(db, owner)
            row = self.owned(db, owner, run_id)
            # Replay of an already accepted answer returns current state without grading twice.
            prior = row.answers.get(qid)
            submitted = {"answer": answer, "option_id": option_id, "dont_know": dont_know}
            if prior:
                if prior["submitted"] != submitted:
                    raise LearningError("answer_already_saved", "That answer was already saved.")
                return self.view(db, row)
            if row.status != "active":
                return self.view(db, row)  # deadline is enforced on the server
            current = next((q for q in row.question_ids if q not in row.answers), None)
            if current != qid:
                raise LearningError("invalid_question", "Answer the current question first.", 422)
            q = db.get(Question, qid)
            if not is_current_question(db, q):
                raise LearningError("content_unavailable", "This question is no longer published.")
            if dont_know and (answer or option_id):
                raise LearningError("invalid_answer", "Choose an answer or I don't know, not both.", 422)
            options = q.snapshot.get("options", [])
            if dont_know:
                value = None
            elif options:
                chosen = next((o for o in options if o["id"] == option_id), None)
                if not chosen or answer:
                    raise LearningError("invalid_answer", "Select one displayed option.", 422)
                value = chosen["value"]
            else:
                if option_id is not None:
                    raise LearningError("invalid_answer", "This item expects a whole number.", 422)
                value = normalized_integer(answer)
            row.answers = {**row.answers, qid: {"submitted": submitted, "correct": value == compute_answer(q.snapshot["validator"])}}
            if len(row.answers) == len(row.question_ids):
                row.status, row.finished_at = "completed", self.clock().isoformat()
            return self.view(db, row)

    def finish(self, owner, run_id):
        with transaction(self.engine) as db:
            self.learning.lock_learner(db, owner)
            row = self.owned(db, owner, run_id)
            row.status, row.finished_at = "completed", self.clock().isoformat()
            return self.view(db, row)

    def history(self, owner):
        with transaction(self.engine) as db:
            rows = db.scalars(select(TimedTest).where(TimedTest.learner_id == owner).order_by(TimedTest.created_at.desc()).limit(30))
            return [{"id": row.id, "status": "completed" if self.clock().isoformat() >= row.deadline else row.status,
                     "created_at": row.created_at, "question_count": len(row.question_ids)} for row in rows]

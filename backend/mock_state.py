from datetime import datetime, timezone
from sqlalchemy import select
from backend.app_models import TimedTest


def active_test(db, learner):
    now = datetime.now(timezone.utc).isoformat()
    return db.scalar(select(TimedTest).where(TimedTest.learner_id == learner,
                     TimedTest.status == "active", TimedTest.deadline > now))

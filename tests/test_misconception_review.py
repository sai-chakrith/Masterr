import copy
import json

import pytest

from scripts import misconception_review as review


def fixture():
    return {"schema_version": 1, "misconceptions": [{
        "id": "percent-test", "skill_id": "percentages",
        "description": "Draft misconception.", "short_fix": "Draft fix.",
        "review_status": "draft",
    }]}


def test_review_approval_requires_reviewer_and_iso_date():
    document = fixture()
    with pytest.raises(ValueError, match="reviewer is required"):
        review.apply_review_rows(document, [{"id": "percent-test", "review_status": "approved"}])
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        review.apply_review_rows(document, [{"id": "percent-test", "review_status": "approved",
                                            "reviewer": "Reviewer", "review_date": "26-10-2026"}])


def test_editing_misconception_copy_revokes_approval(tmp_path, monkeypatch):
    path = tmp_path / "misconceptions.json"
    monkeypatch.setattr(review, "PATH", path)
    monkeypatch.setattr(review, "load_questions", lambda: [])
    document = fixture()
    review.apply_review_rows(copy.deepcopy(document), [{"id": "percent-test", "review_status": "approved",
                                                        "reviewer": "Reviewer", "review_date": "2026-10-26"}])
    approved = json.loads(path.read_text(encoding="utf-8"))
    assert approved["misconceptions"][0]["review_status"] == "approved"
    changed = review.apply_content_rows(approved, [{
        "id": "percent-test", "skill_id": "percentages",
        "description": "Revised draft misconception.", "short_fix": "Revised draft fix.",
    }])
    assert changed == ["percent-test"]
    revised = json.loads(path.read_text(encoding="utf-8"))
    assert revised["misconceptions"][0]["review_status"] == "draft"
    assert "review" not in revised["misconceptions"][0]

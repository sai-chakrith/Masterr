import copy

import pytest

from backend.numbers.bank import load_questions
from scripts.question_bank import apply_content_rows, apply_review_rows


def draft_document():
    question = copy.deepcopy(load_questions()[0])
    question.pop("options", None)  # This fixture isolates question copy/review, not tagged-MCQ approval.
    question["version"] = 1
    question["review_status"] = "draft"
    question.pop("review", None)
    return {"questions": [question]}, question["id"]


def test_human_approval_requires_reviewer_and_iso_date_and_versions_content():
    document, qid = draft_document()
    changed = apply_review_rows(document, [{
        "id": qid, "review_status": "approved", "reviewer": "Reviewer A",
        "review_date": "2026-10-26", "review_note": "Checked answer and explanation",
    }])
    assert changed == [qid]
    question = document["questions"][0]
    assert question["version"] == 2
    assert question["review"] == {
        "reviewer": "Reviewer A", "date": "2026-10-26", "note": "Checked answer and explanation",
    }
    assert apply_review_rows(document, [{
        "id": qid, "review_status": "approved", "reviewer": "Reviewer A",
        "review_date": "2026-10-26", "review_note": "Checked answer and explanation",
    }]) == []
    assert question["version"] == 2


@pytest.mark.parametrize("row", [
    {"review_status": "approved", "reviewer": "", "review_date": "2026-10-26"},
    {"review_status": "approved", "reviewer": "Reviewer A", "review_date": "26-10-2026"},
])
def test_approval_rejects_missing_human_provenance(row):
    document, qid = draft_document()
    with pytest.raises(ValueError):
        apply_review_rows(document, [{"id": qid, **row}])
    assert document["questions"][0]["review_status"] == "draft"


def test_withdrawal_requires_attribution_and_draft_removes_review_record():
    document, qid = draft_document()
    question = document["questions"][0]
    question.update(version=4, review_status="approved",
                    review={"reviewer": "Reviewer A", "date": "2026-10-20"})
    assert apply_review_rows(document, [{
        "id": qid, "review_status": "withdrawn", "reviewer": "Reviewer B",
        "review_date": "2026-10-26",
    }]) == [qid]
    question = document["questions"][0]
    assert question["version"] == 5 and question["review_status"] == "withdrawn"
    assert apply_review_rows(document, [{"id": qid, "review_status": "draft"}]) == [qid]
    question = document["questions"][0]
    assert question["version"] == 6 and "review" not in question


def test_content_edit_creates_unapproved_version_and_arithmetic_changes_are_validated():
    document, qid = draft_document()
    question = document["questions"][0]
    question.update(version=2, review_status="approved",
                    review={"reviewer": "Reviewer A", "date": "2026-10-20"})
    assert apply_content_rows(document, [{"id": qid, "prompt": question["prompt"] + " Show your reasoning."}]) == [qid]
    question = document["questions"][0]
    assert question["version"] == 3 and question["review_status"] == "draft"
    assert "review" not in question

    before = copy.deepcopy(document["questions"])
    with pytest.raises(ValueError, match="invalid bank"):
        apply_content_rows(document, [{"id": qid, "answer": str(question["answer"] + 1)}])
    assert document["questions"] == before

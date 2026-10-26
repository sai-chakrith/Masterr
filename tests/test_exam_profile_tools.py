import pytest

from backend.exam_profiles import approved_profiles
from scripts.exam_profiles import apply_profile_rows, approve_document


def test_profile_content_edit_returns_to_draft_then_requires_explicit_review():
    source = {
        "schema_version": 1,
        "status": "approved",
        "profiles": [{"id": "old", "name": "Old", "target_skill_ids": ["divisibility"],
                      "review": {"reviewer": "reviewer", "date": "2026-10-26"}}],
    }
    rows = [{
        "id": "bank-po", "name": "Bank PO",
        "target_skill_ids": '["digits-cyclicity"]',
        "default_mastery_bar": "0.75",
        "topic_bars": '{"digits-cyclicity": 0.8}',
    }]
    draft = apply_profile_rows(source, rows)
    assert draft["status"] == "draft" and draft["schema_version"] == 2
    assert "review" not in draft["profiles"][0]
    with pytest.raises(ValueError, match="reviewer is required"):
        approve_document(draft, " ", "2026-10-26")
    approved = approve_document(draft, "Reviewer A", "2026-10-26")
    assert approved["schema_version"] == 3
    assert approved_profiles(approved)[0]["id"] == "bank-po"


def test_profile_tool_rejects_invalid_content_and_non_iso_review_date():
    source = {"schema_version": 1, "status": "draft", "profiles": []}
    row = {"id": "bad", "name": "Bad", "target_skill_ids": '["unknown-skill"]',
           "default_mastery_bar": "0.75", "topic_bars": "{}"}
    with pytest.raises(ValueError, match="known curriculum"):
        apply_profile_rows(source, [row])
    good = {**row, "id": "ok", "target_skill_ids": '["divisibility"]'}
    draft = apply_profile_rows(source, [good])
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        approve_document(draft, "Reviewer A", "26-10-2026")

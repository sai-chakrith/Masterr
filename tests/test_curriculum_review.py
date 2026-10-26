import copy

import pytest

from backend.curriculum import load_curriculum, validate_curriculum
from scripts.curriculum_review import approve_document, mark_draft


def test_curriculum_approval_records_reviewer_and_detects_content_changes():
    source = load_curriculum()
    approved = approve_document(source, "Reviewer A", "2026-10-26")
    assert approved["schema_version"] == source["schema_version"] + 1
    assert validate_curriculum(approved) == []
    tampered = copy.deepcopy(approved)
    tampered["skills"][0]["lesson"] += " Changed after sign-off."
    assert any("checksum" in error for error in validate_curriculum(tampered))
    draft = mark_draft(approved)
    assert draft["status"] == "draft"
    assert "review" not in draft and "approval_checksum" not in draft
    assert validate_curriculum(draft) == []


def test_curriculum_approval_requires_valid_reviewer_date():
    with pytest.raises(ValueError, match="reviewer is required"):
        approve_document(load_curriculum(), " ", "2026-10-26")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        approve_document(load_curriculum(), "Reviewer A", "26-10-2026")

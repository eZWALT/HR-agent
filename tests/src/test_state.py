import pytest
from src.hr_agent.state import CandidateInfo, ValidationResult, EvaluationResult, get_missing_fields, REQUIRED_FIELDS


class TestCandidateInfo:
    def test_defaults_all_none(self):
        c = CandidateInfo()
        assert c.full_name is None
        assert c.has_license is None
        assert c.city is None
        assert c.experience_years is None
        assert c.experience_platform is None
        assert c.availability is None
        assert c.preferred_schedule is None
        assert c.start_date is None
        assert c.language == "EN"

    def test_language_default_es(self):
        c = CandidateInfo(language="ES")
        assert c.language == "ES"

    def test_full_populated(self):
        c = CandidateInfo(
            full_name="Juan Pérez",
            has_license=True,
            city="Madrid",
            experience_years=3,
            experience_platform="Glovo",
            availability="full-time",
            preferred_schedule="morning",
            start_date="ASAP",
            language="ES",
        )
        assert c.full_name == "Juan Pérez"
        assert c.has_license is True
        assert c.experience_years == 3

    def test_negative_experience_allowed(self):
        c = CandidateInfo(experience_years=0)
        assert c.experience_years == 0

    def test_model_dump_roundtrip(self):
        c = CandidateInfo(full_name="Test", has_license=True, city="Madrid")
        d = c.model_dump()
        c2 = CandidateInfo(**d)
        assert c2.full_name == "Test"
        assert c2.has_license is True
        assert c2.city == "Madrid"


class TestValidationResult:
    def test_defaults(self):
        v = ValidationResult(is_valid=True, is_off_topic=False)
        assert v.is_valid is True
        assert v.is_off_topic is False
        assert v.feedback is None
        assert v.cleared_fields == []

    def test_with_feedback(self):
        v = ValidationResult(
            is_valid=False,
            is_off_topic=False,
            feedback="City not in service area",
            cleared_fields=["city"],
        )
        assert v.is_valid is False
        assert v.cleared_fields == ["city"]


class TestEvaluationResult:
    def test_basic(self):
        e = EvaluationResult(score=75, summary="Good candidate.")
        assert e.score == 75
        assert e.summary == "Good candidate."

    def test_disqualify_score(self):
        e = EvaluationResult(score=10, summary="No license.")
        assert e.score == 10


class TestGetMissingFields:
    def test_all_missing_when_empty(self):
        c = CandidateInfo()
        missing = get_missing_fields(c)
        assert len(missing) == 8
        assert "full_name" in missing
        assert "preferred_schedule" in missing

    def test_none_missing_when_complete(self):
        c = CandidateInfo(
            full_name="X",
            has_license=True,
            city="Madrid",
            experience_years=1,
            experience_platform="Uber Eats",
            availability="part-time",
            preferred_schedule="flexible",
            start_date="tomorrow",
        )
        assert get_missing_fields(c) == []

    def test_partial(self):
        c = CandidateInfo(full_name="X", has_license=True)
        missing = get_missing_fields(c)
        assert "full_name" not in missing
        assert "has_license" not in missing
        assert "city" in missing
        assert len(missing) == 6

    def test_zero_is_not_missing(self):
        c = CandidateInfo(experience_years=0)
        missing = get_missing_fields(c)
        assert "experience_years" not in missing

    def test_required_fields_count(self):
        assert len(REQUIRED_FIELDS) == 8

    def test_required_fields_match_candidate_attrs(self):
        c = CandidateInfo()
        for field in REQUIRED_FIELDS:
            assert hasattr(c, field)

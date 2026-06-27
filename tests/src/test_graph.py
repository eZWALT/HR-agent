import pytest
from unittest.mock import patch, MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from src.hr_agent.state import (
    CandidateInfo,
    AgentState,
    ValidationResult,
    get_missing_fields,
)


class TestCityInServiceArea:
    def test_madrid_matches(self):
        from src.hr_agent.graph import _city_in_service_area
        with patch("src.hr_agent.graph.SERVICE_AREAS", ["madrid", "barcelona"]):
            assert _city_in_service_area("Madrid") is True
            assert _city_in_service_area("madrid") is True

    def test_case_insensitive(self):
        from src.hr_agent.graph import _city_in_service_area
        with patch("src.hr_agent.graph.SERVICE_AREAS", ["madrid"]):
            assert _city_in_service_area("MADRID") is True
            assert _city_in_service_area("MaDrId") is True

    def test_substring_match(self):
        from src.hr_agent.graph import _city_in_service_area
        with patch("src.hr_agent.graph.SERVICE_AREAS", ["madrid"]):
            assert _city_in_service_area("Madrid, Spain") is True

    def test_unknown_city_fails(self):
        from src.hr_agent.graph import _city_in_service_area
        with patch("src.hr_agent.graph.SERVICE_AREAS", ["madrid"]):
            assert _city_in_service_area("Wakanda") is False
            assert _city_in_service_area("Paris") is False

    def test_none_city_passes(self):
        from src.hr_agent.graph import _city_in_service_area
        with patch("src.hr_agent.graph.SERVICE_AREAS", ["madrid"]):
            assert _city_in_service_area(None) is True
            assert _city_in_service_area("") is True


class TestConversationHelpers:
    def test_conversation_messages_filters_system(self):
        from src.hr_agent.graph import _conversation_messages
        from langchain_core.messages import SystemMessage

        state = {
            "messages": [
                SystemMessage(content="system prompt"),
                HumanMessage(content="hello"),
                AIMessage(content="hi there"),
            ]
        }
        conv = _conversation_messages(state)
        assert len(conv) == 2
        assert conv[0].type == "human"
        assert conv[1].type == "ai"

    def test_last_human_message(self):
        from src.hr_agent.graph import _last_human_message

        messages = [
            HumanMessage(content="first"),
            AIMessage(content="reply"),
            HumanMessage(content="second"),
        ]
        last = _last_human_message(messages)
        assert last.content == "second"

    def test_last_human_message_none(self):
        from src.hr_agent.graph import _last_human_message
        assert _last_human_message([]) is None
        assert _last_human_message([AIMessage(content="hi")]) is None

    def test_format_conversation(self):
        from src.hr_agent.graph import _format_conversation
        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="hi back"),
        ]
        text = _format_conversation(messages)
        assert "User: hello" in text
        assert "Assistant: hi back" in text


class TestRouteAfterValidator:
    def _make_state(self, candidate=None, is_off_topic=False, validation_feedback=None):
        return {
            "messages": [HumanMessage(content="test")],
            "candidate": candidate or CandidateInfo(),
            "is_qualified": True,
            "is_off_topic": is_off_topic,
            "validation_feedback": validation_feedback,
            "termination_reason": None,
            "score": None,
            "recruiter_summary": None,
        }

    def test_no_license_routes_to_disqualify(self):
        from src.hr_agent.graph import route_after_validator
        candidate = CandidateInfo(has_license=False)
        state = self._make_state(candidate=candidate)
        assert route_after_validator(state) == "disqualify"

    def test_city_outside_service_area_routes_to_disqualify(self):
        from src.hr_agent.graph import route_after_validator
        candidate = CandidateInfo(has_license=True, city="Wakanda")
        state = self._make_state(candidate=candidate)
        with patch("src.hr_agent.graph._city_in_service_area", return_value=False):
            assert route_after_validator(state) == "disqualify"

    def test_validation_feedback_routes_to_chatbot(self):
        from src.hr_agent.graph import route_after_validator
        candidate = CandidateInfo(has_license=True, full_name="Test")
        state = self._make_state(
            candidate=candidate,
            validation_feedback="answers seem inconsistent",
        )
        assert route_after_validator(state) == "chatbot"

    def test_off_topic_routes_to_chatbot(self):
        from src.hr_agent.graph import route_after_validator
        candidate = CandidateInfo(has_license=True)
        state = self._make_state(candidate=candidate, is_off_topic=True)
        assert route_after_validator(state) == "chatbot"

    def test_missing_fields_routes_to_chatbot(self):
        from src.hr_agent.graph import route_after_validator
        candidate = CandidateInfo(has_license=True, full_name="Test")
        state = self._make_state(candidate=candidate)
        assert route_after_validator(state) == "chatbot"

    def test_all_fields_complete_routes_to_qualified(self):
        from src.hr_agent.graph import route_after_validator
        candidate = CandidateInfo(
            full_name="Juan",
            has_license=True,
            city="Madrid",
            experience_years=2,
            experience_platform="Glovo",
            availability="full-time",
            preferred_schedule="morning",
            start_date="ASAP",
        )
        state = self._make_state(candidate=candidate)
        with patch("src.hr_agent.graph._city_in_service_area", return_value=True):
            assert route_after_validator(state) == "qualified"

    def test_no_candidate_routes_to_chatbot(self):
        from src.hr_agent.graph import route_after_validator
        state = self._make_state(candidate=None)
        state["candidate"] = None
        assert route_after_validator(state) == "chatbot"


class TestAnalyzerNode:
    def test_analyzer_extracts_and_merges(self):
        from src.hr_agent.graph import analyzer

        existing = CandidateInfo(full_name="Juan", has_license=True)
        new_data = CandidateInfo(full_name="Juan", has_license=True, city="Madrid", language="ES")

        state = {
            "messages": [HumanMessage(content="I live in Madrid")],
            "candidate": existing,
            "is_qualified": True,
            "is_off_topic": False,
            "validation_feedback": None,
            "termination_reason": None,
            "score": None,
            "recruiter_summary": None,
        }

        with patch("src.hr_agent.graph._analyzer_llm") as mock_llm:
            mock_llm.invoke.return_value = new_data
            result = analyzer(state)

        assert isinstance(result, dict) or hasattr(result, "__getitem__")
        candidate = result["candidate"] if isinstance(result, dict) else result.get("candidate")
        assert candidate.city == "Madrid"
        assert candidate.full_name == "Juan"  # preserved
        assert candidate.has_license is True  # preserved

    def test_analyzer_no_conversation_returns_state(self):
        from src.hr_agent.graph import analyzer
        state = {
            "messages": [],
            "candidate": CandidateInfo(),
            "is_qualified": True,
            "is_off_topic": False,
            "validation_feedback": None,
            "termination_reason": None,
            "score": None,
            "recruiter_summary": None,
        }
        result = analyzer(state)
        candidate = result.get("candidate") if isinstance(result, dict) else result["candidate"]
        assert candidate.full_name is None

    def test_analyzer_llm_failure_returns_state(self):
        from src.hr_agent.graph import analyzer

        state = {
            "messages": [HumanMessage(content="hello")],
            "candidate": CandidateInfo(full_name="Test"),
            "is_qualified": True,
            "is_off_topic": False,
            "validation_feedback": None,
            "termination_reason": None,
            "score": None,
            "recruiter_summary": None,
        }

        with patch("src.hr_agent.graph._analyzer_llm") as mock_llm:
            mock_llm.invoke.side_effect = Exception("LLM down")
            result = analyzer(state)

        candidate = result.get("candidate") if isinstance(result, dict) else result["candidate"]
        assert candidate.full_name == "Test"  # preserved on failure


class TestValidatorNode:
    def _make_state(self, candidate, messages=None):
        return {
            "messages": messages or [HumanMessage(content="test")],
            "candidate": candidate,
            "is_qualified": True,
            "is_off_topic": False,
            "validation_feedback": None,
            "termination_reason": None,
            "score": None,
            "recruiter_summary": None,
        }

    def test_no_license_immediate_knockout(self):
        from src.hr_agent.graph import validator
        candidate = CandidateInfo(has_license=False)
        state = self._make_state(candidate)
        result = validator(state)
        assert result["is_qualified"] is False

    def test_valid_data_passes(self):
        from src.hr_agent.graph import validator
        candidate = CandidateInfo(has_license=True, city="Madrid")
        state = self._make_state(candidate)
        valid_result = ValidationResult(is_valid=True, is_off_topic=False)
        with patch("src.hr_agent.graph._validator_llm") as mock_llm:
            mock_llm.invoke.return_value = valid_result
            result = validator(state)
        assert result.get("validation_feedback") is None
        assert result.get("is_off_topic") is False

    def test_clears_invalid_field(self):
        from src.hr_agent.graph import validator
        candidate = CandidateInfo(has_license=True, city="Wakanda")
        state = self._make_state(candidate)
        invalid_result = ValidationResult(
            is_valid=False,
            is_off_topic=False,
            feedback="Wakanda is not a real city",
            cleared_fields=["city"],
        )
        with patch("src.hr_agent.graph._validator_llm") as mock_llm:
            mock_llm.invoke.return_value = invalid_result
            result = validator(state)
        candidate = result["candidate"]
        assert candidate.city is None
        assert result["validation_feedback"] == "Wakanda is not a real city"

    def test_off_topic_detected(self):
        from src.hr_agent.graph import validator
        candidate = CandidateInfo(has_license=True)
        state = self._make_state(candidate, messages=[HumanMessage(content="tell me a joke")])
        off_topic_result = ValidationResult(
            is_valid=False,
            is_off_topic=True,
            feedback="User is off-topic, redirect to screening",
            cleared_fields=[],
        )
        with patch("src.hr_agent.graph._validator_llm") as mock_llm:
            mock_llm.invoke.return_value = off_topic_result
            result = validator(state)
        assert result["is_off_topic"] is True
        assert "off-topic" in result["validation_feedback"].lower()

    def test_llm_failure_returns_state(self):
        from src.hr_agent.graph import validator
        candidate = CandidateInfo(has_license=True, city="Madrid")
        state = self._make_state(candidate)
        with patch("src.hr_agent.graph._validator_llm") as mock_llm:
            mock_llm.invoke.side_effect = Exception("LLM down")
            result = validator(state)
        assert result.get("validation_feedback") is None

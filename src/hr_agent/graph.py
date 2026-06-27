from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from loguru import logger

from .llm import get_llm
from .prompts import (
    ANALYZER_PROMPT,
    CHATBOT_PROMPT_NORMAL,
    CHATBOT_PROMPT_OFF_TOPIC,
    CHATBOT_PROMPT_VALIDATION,
    DISQUALIFY_CLOSING_CITY,
    DISQUALIFY_CLOSING_GENERIC,
    DISQUALIFY_CLOSING_LICENSE,
    EVALUATOR_PROMPT,
    QUALIFIED_CLOSING,
    SERVICE_AREAS,
    VALIDATOR_PROMPT,
    language_label,
)
from .state import (
    AgentState,
    CandidateInfo,
    EvaluationResult,
    ValidationResult,
    get_missing_fields,
)

_base_llm = get_llm(temperature=0, streaming=False)
_chatbot_llm = get_llm(temperature=0.7, streaming=True)
_analyzer_llm = _base_llm.with_structured_output(CandidateInfo)
_validator_llm = _base_llm.with_structured_output(ValidationResult)
_evaluator_llm = _base_llm.with_structured_output(EvaluationResult)

CLIENT_SLUG = os.getenv("CLIENT_SLUG", "grupo-sazon")
REPORTS_DIR = Path("reports") / "candidates"


def _load_core_info() -> dict:
    path = f"data/{CLIENT_SLUG}/core-info.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "client_name": "Grupo Sazón",
            "assistant_name": "María",
            "emoji": "🌶️",
        }


_CORE = _load_core_info()
_CLIENT_NAME = _CORE.get("client_name", "Grupo Sazón")
_ASSISTANT_NAME = _CORE.get("assistant_name", "María")
_EMOJI = _CORE.get("emoji", "🌶️")


def _conversation_messages(state: AgentState) -> list:
    return [m for m in state["messages"] if getattr(m, "type", "") in ("human", "ai")]


def _format_conversation(messages: list) -> str:
    return "\n".join(
        f"{'User' if getattr(m, 'type', '') == 'human' else 'Assistant'}: {m.content}"
        for m in messages
    )


def _last_human_message(messages: list):
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human":
            return msg
    return None


def _city_in_service_area(city: str | None) -> bool:
    if not city:
        return True
    city_lower = city.lower().strip()
    for area in SERVICE_AREAS:
        if area in city_lower or city_lower in area:
            return True
    return False


# ── Node: Analyzer ─────────────────────────────────────────────

def analyzer(state: AgentState) -> dict:
    conversation = _conversation_messages(state)
    if not conversation:
        return state

    last_human = _last_human_message(conversation)
    if not last_human:
        return state

    candidate = state.get("candidate") or CandidateInfo()

    prompt = ANALYZER_PROMPT.format(
        current_data=candidate.model_dump_json(),
        conversation=_format_conversation(conversation),
    )

    try:
        new_info = _analyzer_llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=str(last_human.content)),
        ])
    except Exception as e:
        logger.error(f"analyzer LLM call failed: {e}")
        return state

    merged = candidate.model_dump()
    new_data = new_info.model_dump(exclude_unset=True, exclude_none=True)
    merged.update(new_data)

    state["candidate"] = CandidateInfo(**merged)
    logger.info(f"analyzer: extracted fields = {list(new_data.keys())}")
    return state


# ── Node: Validator ────────────────────────────────────────────

def validator(state: AgentState) -> dict:
    candidate = state.get("candidate")
    if not candidate:
        return state

    messages = state.get("messages", [])
    state["is_off_topic"] = False
    state["validation_feedback"] = None

    if candidate.has_license is False:
        state["is_qualified"] = False
        logger.info("validator: knockout — no license")
        return state

    last_human = _last_human_message(messages)
    if not last_human:
        return state

    prompt = VALIDATOR_PROMPT.format(
        service_areas=", ".join(SERVICE_AREAS),
        candidate_json=candidate.model_dump_json(),
        last_message=str(last_human.content),
    )

    try:
        result = _validator_llm.invoke([SystemMessage(content=prompt)])
    except Exception as e:
        logger.error(f"validator LLM call failed: {e}")
        return state

    if not result.is_valid or result.is_off_topic:
        state["is_off_topic"] = result.is_off_topic
        state["validation_feedback"] = result.feedback

        if result.cleared_fields:
            for field in result.cleared_fields:
                if hasattr(candidate, field):
                    setattr(candidate, field, None)
            state["candidate"] = candidate
            logger.info(f"validator: cleared fields = {result.cleared_fields}")

    return state


# ── Node: Chatbot (streaming) ─────────────────────────────────

def chatbot(state: AgentState) -> dict:
    candidate = state.get("candidate") or CandidateInfo()
    conversation = _conversation_messages(state)

    missing = get_missing_fields(candidate)

    if missing:
        field_to_ask = missing[0]
        lang = language_label(candidate.language)
        conv_text = _format_conversation(conversation)

        if state.get("is_off_topic"):
            prompt = CHATBOT_PROMPT_OFF_TOPIC.format(
                assistant_name=_ASSISTANT_NAME,
                client_name=_CLIENT_NAME,
                emoji=_EMOJI,
                validation_feedback=state.get("validation_feedback", ""),
                missing_field=field_to_ask,
                language_label=lang,
            )
        elif state.get("validation_feedback"):
            prompt = CHATBOT_PROMPT_VALIDATION.format(
                assistant_name=_ASSISTANT_NAME,
                client_name=_CLIENT_NAME,
                emoji=_EMOJI,
                validation_feedback=state.get("validation_feedback", ""),
                missing_field=field_to_ask,
                language_label=lang,
            )
        else:
            prompt = CHATBOT_PROMPT_NORMAL.format(
                assistant_name=_ASSISTANT_NAME,
                client_name=_CLIENT_NAME,
                emoji=_EMOJI,
                missing_field=field_to_ask,
                language_label=lang,
                candidate_json=candidate.model_dump_json(),
                conversation=conv_text,
            )

        response = _chatbot_llm.invoke([SystemMessage(content=prompt)] + conversation)
        return {"messages": [response]}

    return state


# ── Node: Qualified ───────────────────────────────────────────

def qualified(state: AgentState) -> dict:
    candidate = state.get("candidate") or CandidateInfo()

    eval_result = _evaluate(candidate, disqualify_note="")
    candidate_fields = candidate.model_dump()
    candidate_summary = json.dumps(candidate_fields, ensure_ascii=False, indent=2)
    
    closing = QUALIFIED_CLOSING.format(client_name=_CLIENT_NAME, emoji=_EMOJI)

    return {
        "messages": [AIMessage(content=closing)],
        "candidate": candidate,
        "score": eval_result.score,
        "recruiter_summary": eval_result.summary,
        "termination_reason": "QUALIFIED",
        "is_qualified": True,
    }


# ── Node: Disqualify ──────────────────────────────────────────

def disqualify(state: AgentState) -> dict:
    candidate = state.get("candidate") or CandidateInfo()

    if candidate.has_license is False:
        reason = "No valid driver's license."
        closing = DISQUALIFY_CLOSING_LICENSE
    elif not _city_in_service_area(candidate.city):
        reason = f"City '{candidate.city}' not in service areas."
        closing = DISQUALIFY_CLOSING_CITY.format(city=candidate.city or "that area")
    else:
        reason = "Does not meet requirements."
        closing = DISQUALIFY_CLOSING_GENERIC

    disqualify_note = f"DISQUALIFICATION REASON: {reason}"
    eval_result = _evaluate(candidate, disqualify_note=disqualify_note)

    return {
        "messages": [AIMessage(content=closing)],
        "candidate": candidate,
        "score": eval_result.score,
        "recruiter_summary": eval_result.summary,
        "termination_reason": "DISQUALIFIED",
        "is_qualified": False,
    }


# ── Node: Save to DB ──────────────────────────────────────────

def save_to_db(state: AgentState) -> dict:
    candidate = state.get("candidate")
    if not candidate:
        return state

    score = state.get("score", 0)
    reason = state.get("termination_reason", "UNKNOWN")

    if reason == "QUALIFIED":
        status = "INTERVIEW"
    elif reason == "DISQUALIFIED":
        status = "REJECTED"
    else:
        status = "WITHDRAWN"

    name = candidate.full_name or "Unknown"
    dummy_email = f"{name.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@dummy.sazon.com"

    message_history = []
    for msg in state.get("messages", []):
        if getattr(msg, "type", "") in ("human", "ai"):
            role = "user" if msg.type == "human" else "bot"
            message_history.append({"role": role, "content": msg.content})

    try:
        from sqlalchemy import create_engine, text
        db_url = os.getenv("DATABASE_URL", "postgresql://sazon:sazon_password@db:5432/sazon_db")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO candidates (
                    full_name, email, location, status,
                    llm_score, ai_summary, message_history, language
                ) VALUES (
                    :name, :email, :city, :status,
                    :score, :summary, CAST(:history AS JSONB), :language
                )
            """), {
                "name": name,
                "email": dummy_email,
                "city": candidate.city,
                "status": status,
                "score": score,
                "summary": state.get("recruiter_summary", ""),
                "history": json.dumps(message_history),
                "language": candidate.language or "EN",
            })
            conn.commit()
        logger.info(f"save_to_db: {name} → {status} (score={score})")
    except Exception as e:
        logger.error(f"save_to_db failed: {e}")

    try:
        _save_markdown_report(candidate, score, status, state.get("recruiter_summary", ""))
    except Exception as e:
        logger.error(f"markdown report save failed: {e}")

    return state


def _save_markdown_report(candidate: CandidateInfo, score: int, status: str, summary: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9]+", "-", (candidate.full_name or "unknown").lower()).strip("-") or "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{ts}-{safe_name}-{status.lower()}.md"
    path = REPORTS_DIR / filename

    header = f"""# Candidate Evaluation Report

- **Name:** {candidate.full_name or 'Unknown'}
- **Status:** {status}
- **Score:** {score}/100
- **Date (UTC):** {datetime.now(timezone.utc).isoformat()}

---

"""
    path.write_text(header + (summary or "No summary generated.") + "\n", encoding="utf-8")


def _evaluate(candidate: CandidateInfo, disqualify_note: str = "") -> EvaluationResult:
    prompt = EVALUATOR_PROMPT.format(
        client_name=_CLIENT_NAME,
        candidate_json=candidate.model_dump_json(),
        disqualify_note=disqualify_note,
    )
    return _evaluator_llm.invoke([SystemMessage(content=prompt)])


# ── Routing ───────────────────────────────────────────────────

def route_after_validator(state: AgentState) -> str:
    candidate = state.get("candidate")
    if not candidate:
        return "chatbot"

    if candidate.has_license is False:
        return "disqualify"

    if candidate.city and not _city_in_service_area(candidate.city):
        return "disqualify"

    if state.get("validation_feedback") or state.get("is_off_topic"):
        return "chatbot"

    missing = get_missing_fields(candidate)
    if missing:
        return "chatbot"

    return "qualified"


# ── Build Graph ───────────────────────────────────────────────

workflow = StateGraph(AgentState)
workflow.add_node("analyzer", analyzer)
workflow.add_node("validator", validator)
workflow.add_node("chatbot", chatbot)
workflow.add_node("qualified", qualified)
workflow.add_node("disqualify", disqualify)
workflow.add_node("save_to_db", save_to_db)

workflow.add_edge(START, "analyzer")
workflow.add_edge("analyzer", "validator")
workflow.add_conditional_edges(
    "validator",
    route_after_validator,
    {"chatbot": "chatbot", "qualified": "qualified", "disqualify": "disqualify"},
)
workflow.add_edge("chatbot", END)
workflow.add_edge("qualified", "save_to_db")
workflow.add_edge("disqualify", "save_to_db")
workflow.add_edge("save_to_db", END)

graph = workflow.compile()

from __future__ import annotations

from typing import Any

from app.config import NET_JSON_PATH
from app.petri.engine import DiagnosisResult, PetriEngine
from app.petri.model import PetriNet
from app.petri.net import TransitionResult
from app.services.session_store import SessionData

_net: PetriNet | None = None


def get_net() -> PetriNet:
    global _net
    if _net is None:
        _net = PetriNet.from_json_path(NET_JSON_PATH)
    return _net


def engine_from_session(session: SessionData) -> PetriEngine:
    state = {
        "answers": session.answers,
        "marking": session.marking_snapshot,
    }
    engine = PetriEngine.from_state(get_net(), state)
    return engine


def parse_section_answers(form_data: dict[str, Any], section_id: str) -> dict[str, bool]:
    net = get_net()
    section = net.get_section(section_id)
    if not section:
        return {}
    answers: dict[str, bool] = {}
    for pid in section.places:
        place = net.places[pid]
        if place.input_type == "exclusive_choice":
            group = place.exclusive_group or pid
            selected = form_data.get(f"group_{group}")
            answers[pid] = selected == pid
        elif place.input_type == "threshold_yes_no":
            answers[pid] = form_data.get(pid) == "yes"
        else:
            answers[pid] = form_data.get(pid) in (True, "true", "on", "yes", "1", pid)
    return answers


def submit_section(
    session: SessionData, section_id: str, new_answers: dict[str, bool]
) -> tuple[PetriEngine, TransitionResult, DiagnosisResult | None]:
    net = get_net()
    section = net.get_section(section_id)
    if section:
        for pid in section.places:
            session.answers[pid] = new_answers.get(pid, False)

    engine = PetriEngine(net)
    engine.rebuild_from_answers(session.answers)

    transition_result = TransitionResult(fired=False)
    sections_done: list[str] = list(session.completed_sections)
    if section_id not in sections_done:
        sections_done.append(section_id)

    ordered = sorted(net.sections, key=lambda s: s.order)
    for sec in ordered:
        if sec.id not in sections_done:
            continue
        transition_result = engine.evaluate_section_transition(sec.id)

    session.completed_sections = sections_done
    session.marking_snapshot = engine.marking.to_dict()
    if transition_result.warning_message:
        session.pending_warning = transition_result.warning_message
        if transition_result.warning_message not in session.warnings:
            session.warnings.append(transition_result.warning_message)

    diagnosis = None
    if section_id == "instrumental":
        diagnosis = engine.finalize()

    return engine, transition_result, diagnosis


def finalize_session(session: SessionData) -> DiagnosisResult:
    engine = engine_from_session(session)
    for section in get_net().sections:
        if section.id not in session.completed_sections:
            engine.evaluate_section_transition(section.id)
    session.marking_snapshot = engine.marking.to_dict()
    return engine.finalize()

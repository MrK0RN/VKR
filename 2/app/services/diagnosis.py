from __future__ import annotations

from typing import Any

from app.config import NET_JSON_PATH
from app.logging.setup import audit_log, get_logger
from app.petri.engine import DiagnosisResult, PetriEngine
from app.petri.model import PetriNet

logger = get_logger("diagnosis")

_net: PetriNet | None = None


def get_net() -> PetriNet:
    global _net
    if _net is None:
        _net = PetriNet.from_json_path(NET_JSON_PATH)
    return _net


def new_engine() -> PetriEngine:
    return PetriEngine(get_net())


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
    session_id: str,
    session: dict[str, Any],
    section_id: str,
    section_answers: dict[str, bool],
) -> dict[str, Any]:
    net = get_net()
    section = net.get_section(section_id)
    if not section:
        raise ValueError(f"Unknown section: {section_id}")

    engine = new_engine()
    engine.recompute_from_answers(session.get("answers", {}))
    result = engine.apply_section(section_id, section_answers)

    session["answers"] = dict(engine.answers)
    session["marking"] = result.marking
    if section_id not in session["completed_sections"]:
        session["completed_sections"].append(section_id)
    if result.warning and result.warning not in session["warnings_shown"]:
        session["warnings_shown"].append(result.warning)

    audit_log(
        "section_submitted",
        session_id=session_id,
        section=section_id,
        marked_places=[p for p, v in section_answers.items() if v],
        scores_after=result.scores,
        transition={
            "id": net.transition_for_section(section_id).id
            if net.transition_for_section(section_id)
            else None,
            "fired": result.transition_fired,
        },
        warning_shown=result.warning,
    )
    logger.info(
        "transition_evaluated",
        session_id=session_id,
        section=section_id,
        fired=result.transition_fired,
        scores=result.scores,
    )
    if result.warning:
        logger.warning("transition_warning_shown", session_id=session_id, message=result.warning)

    return {
        "scores": result.scores,
        "warning": result.warning,
        "intermediate_marked": result.intermediate_marked,
    }


def finalize_diagnosis(session_id: str, session: dict[str, Any]) -> DiagnosisResult:
    engine = new_engine()
    engine.recompute_from_answers(session.get("answers", {}))
    net = get_net()
    for section in net.sections:
        engine.evaluate_transition_for_section(section.id)
    result = engine.finalize()
    session["marking"] = engine.marking.to_dict()

    audit_log(
        "diagnosis_completed",
        session_id=session_id,
        scores_after=result.scores,
        winner=result.winner,
        tie=result.tie,
    )
    logger.info(
        "diagnosis_completed",
        session_id=session_id,
        hyper=result.scores.get("score_hyper"),
        atrophic=result.scores.get("score_atrophic"),
        winner=result.winner,
    )
    return result

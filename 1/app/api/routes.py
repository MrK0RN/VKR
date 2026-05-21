from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, SESSION_COOKIE_NAME, SESSION_TTL_SECONDS
from app.logging.setup import get_logger
from app.services.diagnosis import (
    finalize_session,
    get_net,
    parse_section_answers,
    submit_section,
)
from app.services.session_store import SessionData, SessionStore

logger = get_logger()
router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))
store = SessionStore(ttl_seconds=SESSION_TTL_SECONDS)


def _get_session_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE_NAME)


def _attach_session_cookie(response: HTMLResponse, session_id: str) -> HTMLResponse:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        max_age=SESSION_TTL_SECONDS,
        samesite="lax",
    )
    return response


def _normalize_step(step: int) -> int:
    net = get_net()
    if step < 1 or step > len(net.sections):
        return 1
    return step


def _section_context(session: SessionData, step: int) -> dict[str, Any]:
    net = get_net()
    step = _normalize_step(step)
    section = net.get_section_by_order(step)
    if not section:
        return {"step": 1, "total_steps": len(net.sections)}

    places: list[dict[str, Any]] = []
    exclusive_groups: dict[str, list[dict[str, Any]]] = {}
    for pid in section.places:
        place = net.places[pid]
        item = {
            "id": place.id,
            "label": place.label,
            "input_type": place.input_type,
            "checked": session.answers.get(place.id, False),
        }
        if place.input_type == "exclusive_choice" and place.exclusive_group:
            exclusive_groups.setdefault(place.exclusive_group, []).append(item)
        else:
            places.append(item)

    for group_name, options in exclusive_groups.items():
        any_selected = any(o["checked"] for o in options)
        for o in options:
            o["group_unspecified"] = not any_selected

    return {
        "section": {
            "id": section.id,
            "title": section.title,
            "order": section.order,
        },
        "places": places,
        "exclusive_groups": exclusive_groups,
        "step": step,
        "total_steps": len(net.sections),
    }


def _render_step(
    request: Request,
    session: SessionData,
    step: int,
    *,
    pending_warning: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    ctx = _section_context(session, step)
    ctx["request"] = request
    ctx["session_id"] = session.session_id
    ctx["pending_warning"] = pending_warning
    response = templates.TemplateResponse(request, "step.html", ctx, status_code=status_code)
    return _attach_session_cookie(response, session.session_id)


def _render_result(request: Request, session: SessionData, *, status_code: int = 200) -> HTMLResponse:
    result = finalize_session(session)
    session.last_result = {
        "score_nodular": result.score_nodular,
        "score_mixed": result.score_mixed,
        "winner": result.winner,
        "winner_label": result.winner_label,
        "tie": result.tie,
    }
    store.save(session)
    forms = get_net().meta.get("forms", {})
    net = get_net()
    intermediate = [
        {"id": ip["id"], "label": ip["label"]}
        for pid in result.intermediate_marked
        if pid in net.intermediate_places
        for ip in [net.intermediate_places[pid]]
    ]
    contributions = [
        {
            "place_id": c.place_id,
            "label": c.label,
            "score_nodular": c.score_nodular,
            "score_mixed": c.score_mixed,
        }
        for c in result.contributions
    ]
    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "request": request,
            "result": {
                "score_nodular": result.score_nodular,
                "score_mixed": result.score_mixed,
                "winner": result.winner,
                "winner_label": result.winner_label,
                "tie": result.tie,
                "instrumental_transition_fired": result.instrumental_transition_fired,
                "contributions": contributions,
            },
            "forms": forms,
            "warnings": list(session.warnings),
            "intermediate": intermediate,
        },
        status_code=status_code,
    )
    return _attach_session_cookie(response, session.session_id)


def _ensure_session(request: Request) -> SessionData:
    session = store.get_or_create(_get_session_id(request))
    store.save(session)
    return session


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session = _ensure_session(request)
    logger.info("session_started", session_id=session.session_id)
    return _render_step(request, session, 1)


@router.get("/step/{step}", response_class=HTMLResponse)
async def step_get(request: Request, step: int):
    session = _ensure_session(request)
    step = _normalize_step(step)
    warning = session.pending_warning
    session.pending_warning = None
    store.save(session)
    return _render_step(request, session, step, pending_warning=warning)


@router.post("/step/{step}", response_class=HTMLResponse)
async def step_post(request: Request, step: int):
    session = _ensure_session(request)
    step = _normalize_step(step)
    net = get_net()
    section = net.get_section_by_order(step)
    if not section:
        return _render_step(request, session, 1)

    form = await request.form()
    form_dict = dict(form)
    new_answers = parse_section_answers(form_dict, section.id)

    start = time.perf_counter()
    engine, transition_result, diagnosis = submit_section(session, section.id, new_answers)
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "transition_evaluated",
        session_id=session.session_id,
        transition_id=transition_result.transition_id,
        fired=transition_result.fired,
        scores=engine.marking.scores,
        duration_ms=round(duration_ms, 2),
    )
    if transition_result.warning_message:
        logger.warning(
            "transition_warning_shown",
            session_id=session.session_id,
            message=transition_result.warning_message,
        )

    session.current_step = step
    store.save(session)

    warning = transition_result.warning_message

    if step >= len(net.sections):
        if diagnosis:
            session.last_result = {
                "score_nodular": diagnosis.score_nodular,
                "score_mixed": diagnosis.score_mixed,
                "winner": diagnosis.winner,
            }
        logger.info(
            "diagnosis_completed",
            session_id=session.session_id,
            score_nodular=engine.marking.scores.get("score_nodular"),
            score_mixed=engine.marking.scores.get("score_mixed"),
            winner=diagnosis.winner if diagnosis else None,
        )
        return _render_result(request, session)

    return _render_step(request, session, step + 1, pending_warning=warning)


@router.get("/result", response_class=HTMLResponse)
async def result_page(request: Request):
    session = _ensure_session(request)
    if not session.completed_sections and not session.answers:
        return _render_step(request, session, 1)
    return _render_result(request, session)


@router.post("/reset", response_class=HTMLResponse)
async def reset(request: Request):
    old_id = _get_session_id(request)
    if old_id:
        store.delete(old_id)
    session = store.create()
    logger.info("session_started", session_id=session.session_id)
    store.save(session)
    return _render_step(request, session, 1)


@router.get("/api/health")
async def health():
    net = get_net()
    return {
        "status": "ok",
        "disease": net.meta.get("disease"),
        "sections": len(net.sections),
        "places": len([p for p in net.places.values() if p.arcs]),
    }

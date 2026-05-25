from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import config
from app.logging.setup import audit_log, get_logger
from app.petri.model import PetriNet
from app.services import diagnosis
from app.services.session_store import session_store

logger = get_logger("routes")

router = APIRouter()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "app" / "web" / "templates"))

def _get_session(request: Request) -> tuple[str | None, dict[str, Any] | None]:
    session_id = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not session_id:
        return None, None
    return session_id, session_store.get(session_id)


def _set_session_cookie(response, session_id: str) -> None:
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_TTL_SECONDS,
    )


def _ensure_session(request: Request) -> tuple[str, dict[str, Any], bool]:
    session_id, session = _get_session(request)
    created = False
    if session is None:
        session_id, session = session_store.create()
        created = True
        audit_log("session_started", session_id=session_id)
    return session_id, session, created


def _with_session_cookie(response, session_id: str):
    _set_session_cookie(response, session_id)
    return response


def _clamp_step(net: PetriNet, step: int) -> int:
    return max(1, min(step, len(net.sections)))


def _place_item(net: PetriNet, pid: str, answers: dict[str, bool]) -> dict[str, Any]:
    p = net.places[pid]
    return {
        "id": pid,
        "label": p.label,
        "input_type": p.input_type,
        "checked": bool(answers.get(pid)),
    }


def _section_context(net: PetriNet, session: dict[str, Any], step: int) -> dict[str, Any]:
    section = net.get_section_by_order(step)
    if not section:
        return {"step": 1, "total_steps": len(net.sections)}

    answers = session.get("answers", {})
    places: list[dict[str, Any]] = []
    exclusive_groups: dict[str, list[dict[str, Any]]] = {}
    lab_groups = None

    if section.laboratory_groups:
        lab_groups = {
            "hyper": {
                "title": "Гипертрофическая ветка (лаборатория)",
                "places": [
                    _place_item(net, pid, answers)
                    for pid in section.laboratory_groups.get("hyper", [])
                ],
            },
            "atrophic": {
                "title": "Атрофическая ветка (лаборатория)",
                "places": [
                    _place_item(net, pid, answers)
                    for pid in section.laboratory_groups.get("atrophic", [])
                ],
            },
        }
        for pid in section.places:
            place = net.places[pid]
            if place.input_type == "exclusive_choice" and place.exclusive_group:
                exclusive_groups.setdefault(place.exclusive_group, []).append(
                    _place_item(net, pid, answers)
                )
    else:
        for pid in section.places:
            place = net.places[pid]
            item = _place_item(net, pid, answers)
            if place.input_type == "exclusive_choice" and place.exclusive_group:
                exclusive_groups.setdefault(place.exclusive_group, []).append(item)
            else:
                places.append(item)

    for options in exclusive_groups.values():
        any_selected = any(o["checked"] for o in options)
        for o in options:
            o["group_unspecified"] = not any_selected

    step_labels = [
        {"order": s.order, "title": s.title}
        for s in sorted(net.sections, key=lambda x: x.order)
    ]

    return {
        "section": {
            "id": section.id,
            "title": section.title,
            "order": section.order,
        },
        "places": places,
        "lab_groups": lab_groups,
        "exclusive_groups": exclusive_groups,
        "step": step,
        "total_steps": len(net.sections),
        "step_labels": step_labels,
    }


def _merge_contributions(result) -> list[dict[str, Any]]:
    by_place: dict[str, dict[str, Any]] = {}
    for item in result.explain_hyper:
        by_place[item["place_id"]] = {
            "place_id": item["place_id"],
            "label": item["label"],
            "score_hyper": item["weight"],
            "score_atrophic": 0,
        }
    for item in result.explain_atrophic:
        row = by_place.setdefault(
            item["place_id"],
            {
                "place_id": item["place_id"],
                "label": item["label"],
                "score_hyper": 0,
                "score_atrophic": 0,
            },
        )
        row["score_atrophic"] = item["weight"]
    return sorted(by_place.values(), key=lambda x: (-(x["score_hyper"] + x["score_atrophic"]), x["place_id"]))


def _render_step(
    request: Request,
    step: int,
    *,
    session_id: str | None = None,
    session: dict[str, Any] | None = None,
    pending_warning: str | None = None,
) -> HTMLResponse:
    net = diagnosis.get_net()
    step = _clamp_step(net, step)

    if session_id is None or session is None:
        session_id, session, _created = _ensure_session(request)

    session["step"] = step
    if pending_warning is None:
        pending_warning = session.pop("pending_warning", None)
    session_store.save(session_id, session)

    ctx = _section_context(net, session, step)
    ctx.update(
        {
            "request": request,
            "pending_warning": pending_warning,
        }
    )
    response = templates.TemplateResponse(request, "step.html", ctx)
    return _with_session_cookie(response, session_id)


def _render_result(
    request: Request,
    session_id: str,
    session: dict[str, Any],
) -> HTMLResponse:
    result = diagnosis.finalize_diagnosis(session_id, session)
    session_store.save(session_id, session)
    net = diagnosis.get_net()
    forms = net.meta.get("forms", {})
    contributions = _merge_contributions(result)

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "request": request,
            "result": {
                "score_hyper": result.scores.get("score_hyper", 0),
                "score_atrophic": result.scores.get("score_atrophic", 0),
                "winner": result.winner,
                "winner_label": result.winner_label,
                "tie": result.tie,
                "contributions": contributions,
            },
            "forms": forms,
            "warnings": list(session.get("warnings_shown", [])),
            "total_steps": len(net.sections),
        },
    )
    return _with_session_cookie(response, session_id)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "hashimoto-diagnosis"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render_step(request, 1)


@router.get("/step/{step}", response_class=HTMLResponse)
async def get_step(request: Request, step: int):
    return _render_step(request, step)


@router.post("/step/{step}", response_class=HTMLResponse)
async def post_step(request: Request, step: int):
    net = diagnosis.get_net()
    step = _clamp_step(net, step)
    section = net.get_section_by_order(step)
    if not section:
        return _render_step(request, 1)

    session_id, session, _created = _ensure_session(request)
    form = await request.form()
    form_dict = dict(form)
    section_answers = diagnosis.parse_section_answers(form_dict, section.id)

    t0 = time.perf_counter()
    try:
        result = diagnosis.submit_section(session_id, session, section.id, section_answers)
    except Exception as exc:
        logger.exception("engine_error", session_id=session_id, error=str(exc))
        audit_log("engine_error", session_id=session_id, error=str(exc))
        raise

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info("step_post", session_id=session_id, step=step, duration_ms=round(duration_ms, 2))

    session_store.save(session_id, session)

    warning = result.get("warning")
    if warning:
        session["pending_warning"] = warning

    if step >= len(net.sections):
        return _render_result(request, session_id, session)

    return _render_step(
        request,
        step + 1,
        session_id=session_id,
        session=session,
        pending_warning=warning,
    )


@router.get("/result", response_class=HTMLResponse)
async def get_result(request: Request):
    session_id, session, _ = _ensure_session(request)
    return _render_result(request, session_id, session)


@router.post("/reset")
async def reset_session(request: Request):
    old_id, _ = _get_session(request)
    if old_id:
        session_store.delete(old_id)
    new_id, session = session_store.create()
    audit_log("session_started", session_id=new_id)
    return _render_step(request, 1, session_id=new_id, session=session)

"""Полный смоук-тест HTTP: все страницы и сценарии должны завершаться без 4xx/5xx."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.diagnosis import get_net

NET = get_net()


def _form_for_section(section_id: str, marked: set[str] | None = None) -> dict[str, str]:
    marked = marked or set()
    section = NET.get_section(section_id)
    data: dict[str, str] = {}
    sex_selected = None
    for pid in section.places:
        place = NET.places[pid]
        if place.input_type == "exclusive_choice":
            if pid in marked:
                sex_selected = pid
        elif place.input_type == "threshold_yes_no":
            data[pid] = "yes" if pid in marked else "no"
        else:
            if pid in marked:
                data[pid] = "on"
    if any(NET.places[p].exclusive_group == "sex" for p in section.places):
        data["group_sex"] = sex_selected or ""
    return data


@pytest.fixture
def client():
    with TestClient(app, follow_redirects=True) as c:
        yield c


def test_static_assets_200(client: TestClient):
    for path in ("/static/style.css", "/static/app.js"):
        r = client.get(path)
        assert r.status_code == 200, f"{path}: {r.status_code}"


def test_health_200(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "Лимфома" in body["disease"]


def test_index_reaches_step1_200(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "Жалобы" in r.text


def test_all_steps_get_200(client: TestClient):
    client.get("/")
    for step in range(1, len(NET.sections) + 1):
        r = client.get(f"/step/{step}")
        assert r.status_code == 200, f"GET /step/{step}: {r.status_code}"
        section = NET.get_section_by_order(step)
        assert section.title in r.text


def test_invalid_step_normalizes_to_step1_200(client: TestClient):
    client.get("/")
    for bad in (0, 99, -1):
        r = client.get(f"/step/{bad}")
        assert r.status_code == 200
        assert "Жалобы" in r.text


def test_full_wizard_empty_answers_200(client: TestClient):
    client.get("/")
    for step in range(1, len(NET.sections) + 1):
        section = NET.get_section_by_order(step)
        r = client.post(f"/step/{step}", data=_form_for_section(section.id))
        assert r.status_code == 200, f"POST step {step}: {r.status_code}"
        if step == len(NET.sections):
            assert "Результат" in r.text
    r = client.get("/result")
    assert r.status_code == 200
    assert "0" in r.text
    assert "Нодулярный" in r.text


def test_full_wizard_with_symptoms_200(client: TestClient):
    client.get("/")
    marked_by_section = {
        "complaints": {"b1", "b4"},
        "examination": {"b19"},
        "laboratory": {"b31"},
        "instrumental": {"b41"},
    }
    for step in range(1, len(NET.sections) + 1):
        section = NET.get_section_by_order(step)
        marked = marked_by_section.get(section.id, set())
        r = client.post(f"/step/{step}", data=_form_for_section(section.id, marked))
        assert r.status_code == 200, f"POST step {step}: {r.status_code}"
        if step == len(NET.sections):
            assert "Результат" in r.text
    r = client.get("/result")
    assert r.status_code == 200
    assert "Нодулярный" in r.text


def test_back_navigation_200(client: TestClient):
    client.get("/")
    client.post("/step/1", data=_form_for_section("complaints", {"b1"}))
    r = client.get("/step/1")
    assert r.status_code == 200
    assert "b1" in r.text or "припухлости" in r.text


def test_reset_200(client: TestClient):
    client.get("/")
    client.post("/step/1", data=_form_for_section("complaints", {"b1"}))
    r = client.post("/reset")
    assert r.status_code == 200
    r2 = client.get("/step/1")
    assert r2.status_code == 200


def test_result_without_session_starts_fresh_200():
    with TestClient(app, follow_redirects=True) as c:
        r = c.get("/result")
        assert r.status_code == 200
        assert "Жалобы" in r.text or "Результат" in r.text


def test_post_invalid_step_200(client: TestClient):
    client.get("/")
    r = client.post("/step/0", data={})
    assert r.status_code == 200
    r2 = client.post("/step/999", data={})
    assert r2.status_code == 200

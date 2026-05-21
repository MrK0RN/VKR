"""Полный HTTP smoke-тест: все пользовательские страницы отдают 200."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.config import SESSION_COOKIE_NAME
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


def _cookie_from_response(response) -> str | None:
    header = response.headers.get("set-cookie", "")
    match = re.search(rf"{SESSION_COOKIE_NAME}=([^;]+)", header)
    return match.group(1) if match else None


def _apply_cookie(client: TestClient, response) -> None:
    value = _cookie_from_response(response)
    if value:
        client.cookies.set(SESSION_COOKIE_NAME, value)


class TestStaticAndHealth:
    def test_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_static_css(self, client: TestClient):
        r = client.get("/static/style.css")
        assert r.status_code == 200
        assert "text/css" in r.headers.get("content-type", "")


class TestGetPages200:
    def test_index_returns_200(self, client: TestClient):
        r = client.get("/")
        assert r.status_code == 200
        _apply_cookie(client, r)
        assert "Жалобы" in r.text

    @pytest.mark.parametrize("step", [1, 2, 3, 4])
    def test_step_pages(self, client: TestClient, step: int):
        r = client.get(f"/step/{step}")
        assert r.status_code == 200, f"step {step}: {r.status_code}"
        _apply_cookie(client, r)

    def test_invalid_step_clamped_to_1(self, client: TestClient):
        r = client.get("/step/0")
        assert r.status_code == 200
        assert "Жалобы" in r.text

    def test_invalid_step_high_clamped(self, client: TestClient):
        r = client.get("/step/99")
        assert r.status_code == 200
        assert "Инструментальные" in r.text

    def test_result_with_session(self, client: TestClient):
        r = client.get("/step/1")
        _apply_cookie(client, r)
        r = client.get("/result")
        assert r.status_code == 200
        assert "Результат" in r.text

    def test_result_without_session_creates_view(self, client: TestClient):
        r = client.get("/result")
        assert r.status_code == 200
        assert "Результат" in r.text
        _apply_cookie(client, r)


class TestPostFlow200AfterRedirect:
    def test_full_survey_flow(self, client: TestClient):
        r = client.get("/step/1")
        assert r.status_code == 200
        _apply_cookie(client, r)

        r = client.post(
            "/step/1",
            data={"b1": "on", "b4": "on"},
        )
        assert r.status_code == 200
        _apply_cookie(client, r)
        assert "Осмотр" in r.text

        r = client.post(
            "/step/2",
            data={"b14": "on", "b17": "on"},
        )
        assert r.status_code == 200
        _apply_cookie(client, r)

        r = client.post(
            "/step/3",
            data={"b23": "yes", "b29": "yes"},
        )
        assert r.status_code == 200
        _apply_cookie(client, r)

        r = client.post(
            "/step/4",
            data={"b37": "on"},
        )
        assert r.status_code == 200
        _apply_cookie(client, r)
        assert "Гипертрофическ" in r.text or "гипертрофическ" in r.text.lower()

    def test_back_navigation_returns_200(self, client: TestClient):
        r = client.get("/step/2")
        _apply_cookie(client, r)
        r = client.get("/step/1")
        assert r.status_code == 200
        assert "Жалобы" in r.text

    def test_reset_flow(self, client: TestClient):
        r = client.get("/step/3")
        _apply_cookie(client, r)
        r = client.post("/reset")
        assert r.status_code == 200
        assert "Жалобы" in r.text

    def test_post_without_prior_cookie_gets_cookie(self, client: TestClient):
        r = client.post("/step/1", data={"b1": "on"})
        assert r.status_code == 200
        assert _cookie_from_response(r) is not None
        assert "Осмотр" in r.text

    def test_empty_complaints_warning_then_200(self, client: TestClient):
        r = client.get("/step/1")
        _apply_cookie(client, r)
        r = client.post("/step/1", data={})
        assert r.status_code == 200
        assert "Не выявлено" in r.text or "alert" in r.text
        assert "Осмотр" in r.text

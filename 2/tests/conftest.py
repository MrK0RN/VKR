"""Изоляция in-memory сессий между тестами."""

import pytest

from app.services.session_store import session_store


@pytest.fixture(autouse=True)
def _clear_sessions():
    session_store.clear_all()
    yield
    session_store.clear_all()

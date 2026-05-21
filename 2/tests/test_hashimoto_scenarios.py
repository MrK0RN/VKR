"""Сценарные тесты по plan.md."""

from __future__ import annotations

from app.config import NET_JSON_PATH
from app.petri.engine import PetriEngine
from app.petri.model import PetriNet
from app.petri.net import SCORE_ATROPHIC, SCORE_HYPER


def _engine() -> PetriEngine:
    return PetriEngine(PetriNet.from_json_path(NET_JSON_PATH))


def test_full_hyper_path():
    e = _engine()
    e.apply_section("complaints", {"b1": True, "b2": True})
    e.apply_section("examination", {"b14": True, "b17": True})
    e.apply_section("laboratory", {"b23": True, "b26": True})
    e.apply_section("instrumental", {"b37": True})
    r = e.finalize()
    assert r.scores[SCORE_HYPER] > r.scores[SCORE_ATROPHIC]
    assert r.winner == "hyper"


def test_full_atrophic_path():
    e = _engine()
    e.apply_section("complaints", {"b5": True, "b6": True})
    e.apply_section("examination", {"b20": True})
    e.apply_section("laboratory", {"b29": True, "b30": True})
    e.apply_section("instrumental", {"b39": True})
    r = e.finalize()
    assert r.scores[SCORE_ATROPHIC] > r.scores[SCORE_HYPER]
    assert r.winner == "atrophic"


def test_empty_instrumental_still_finalizes():
    e = _engine()
    e.apply_section("complaints", {"b4": True})
    e.apply_section("examination", {})
    e.apply_section("laboratory", {})
    e.apply_section("instrumental", {})
    r = e.finalize()
    assert r.scores[SCORE_HYPER] >= 1

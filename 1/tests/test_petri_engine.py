from pathlib import Path

import pytest

from app.config import NET_JSON_PATH
from app.petri.engine import PetriEngine
from app.petri.model import PetriNet


@pytest.fixture
def net() -> PetriNet:
    return PetriNet.from_json_path(NET_JSON_PATH)


@pytest.fixture
def engine(net: PetriNet) -> PetriEngine:
    return PetriEngine(net)


def test_empty_marking_zero_scores(engine: PetriEngine):
    result = engine.finalize()
    assert result.score_nodular == 0
    assert result.score_mixed == 0
    assert result.tie is True


def test_b4_dual_weights(engine: PetriEngine):
    engine.apply_user_input("b4", True)
    assert engine.marking.scores["score_nodular"] == 1
    assert engine.marking.scores["score_mixed"] == 2


def test_nodular_complaints_branch(engine: PetriEngine):
    engine.apply_user_input("b1", True)
    tr = engine.evaluate_section_transition("complaints")
    assert tr.nodular_fired is True
    assert engine.marking.places.get("b9") == 1


def test_instrumental_any_one_marked(engine: PetriEngine):
    engine.apply_user_input("b44", True)
    tr = engine.evaluate_section_transition("instrumental")
    assert tr.fired is True
    assert engine.marking.places.get("b42") == 1
    assert engine.marking.places.get("b43") == 1


def test_exclusive_sex(engine: PetriEngine):
    engine.apply_user_input("b19", True)
    assert engine.marking.scores["score_nodular"] == 1
    engine.apply_user_input("b20", True)
    assert "b19" not in engine.marking.places
    assert engine.marking.scores["score_nodular"] == 1


def test_examination_to_lab_mixed_threshold(engine: PetriEngine):
    for pid in ("b21", "b22", "b23", "b24", "b25"):
        engine.apply_user_input(pid, True)
    tr = engine.evaluate_section_transition("examination")
    assert tr.mixed_fired is False

    engine.apply_user_input("b18", True)
    tr = engine.evaluate_section_transition("examination")
    assert tr.mixed_fired is True
    assert engine.marking.places.get("b12") == 1


def test_laboratory_to_instrumental_thresholds(engine: PetriEngine):
    engine.apply_user_input("b29", True)
    engine.apply_user_input("b30", True)
    engine.apply_user_input("b31", True)
    tr = engine.evaluate_section_transition("laboratory")
    assert tr.nodular_fired is False
    assert tr.mixed_fired is False

    engine.apply_user_input("b28", True)
    tr = engine.evaluate_section_transition("laboratory")
    assert tr.nodular_fired is True
    assert engine.marking.places.get("b26") == 1

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
    assert engine.marking.scores["score_nodular"] == 2
    engine.apply_user_input("b20", True)
    assert "b19" not in engine.marking.places
    assert engine.marking.scores["score_nodular"] == 1

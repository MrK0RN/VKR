"""Unit-тесты PetriEngine для сети Хашимото."""

from __future__ import annotations

import pytest

from app.config import NET_JSON_PATH
from app.petri.engine import PetriEngine
from app.petri.model import PetriNet
from app.petri.net import SCORE_ATROPHIC, SCORE_HYPER


@pytest.fixture
def net() -> PetriNet:
    return PetriNet.from_json_path(NET_JSON_PATH)


@pytest.fixture
def engine(net: PetriNet) -> PetriEngine:
    return PetriEngine(net)


def test_only_b1_hyper_2(engine: PetriEngine):
    engine.recompute_from_answers({"b1": True})
    assert engine.marking.scores[SCORE_HYPER] == 2
    assert engine.marking.scores[SCORE_ATROPHIC] == 0


def test_b4_both_branches(engine: PetriEngine):
    engine.recompute_from_answers({"b4": True})
    assert engine.marking.scores[SCORE_HYPER] == 1
    assert engine.marking.scores[SCORE_ATROPHIC] == 1


def test_b5_mixed_weights(engine: PetriEngine):
    engine.recompute_from_answers({"b5": True})
    assert engine.marking.scores[SCORE_HYPER] == 1
    assert engine.marking.scores[SCORE_ATROPHIC] == 2


def test_only_b20_atrophic_2(engine: PetriEngine):
    engine.recompute_from_answers({"b20": True})
    assert engine.marking.scores[SCORE_HYPER] == 0
    assert engine.marking.scores[SCORE_ATROPHIC] == 2


def test_empty_survey_zero_zero(engine: PetriEngine):
    engine.recompute_from_answers({})
    result = engine.finalize()
    assert result.scores[SCORE_HYPER] == 0
    assert result.scores[SCORE_ATROPHIC] == 0
    assert result.winner is None
    assert result.tie is True


def test_only_b39_instrumental(engine: PetriEngine, net: PetriNet):
    engine.recompute_from_answers({"b39": True})
    tr = engine.evaluate_transition_for_section("instrumental")
    assert tr.fired is True
    assert engine.marking.scores[SCORE_ATROPHIC] >= 1


def test_sex_optional_no_penalty(engine: PetriEngine):
    engine.recompute_from_answers({"b14": True})
    assert engine.marking.scores[SCORE_HYPER] == 2


def test_complaints_transition_warning(engine: PetriEngine):
    engine.recompute_from_answers({})
    tr = engine.evaluate_transition_for_section("complaints")
    assert tr.fired is False
    assert tr.warning_message is not None
    assert "ХАТ" in tr.warning_message


def test_complaints_sets_intermediate_b10(engine: PetriEngine):
    engine.recompute_from_answers({"b1": True})
    tr = engine.evaluate_transition_for_section("complaints")
    assert tr.hyper_branch_fired is True
    assert "b10" in tr.intermediate_marked


def test_idempotent_recompute(engine: PetriEngine):
    answers = {"b1": True, "b4": True}
    engine.recompute_from_answers(answers)
    s1 = dict(engine.marking.scores)
    engine.recompute_from_answers(answers)
    assert engine.marking.scores == s1


def test_finalize_hyper_wins(engine: PetriEngine):
    engine.recompute_from_answers({"b1": True, "b14": True})
    r = engine.finalize()
    assert r.winner == "hyper"
    assert r.tie is False


def test_apply_section_merges_answers(engine: PetriEngine):
    engine.apply_section("complaints", {"b1": True})
    engine.apply_section("examination", {"b20": True})
    assert engine.marking.scores[SCORE_HYPER] == 2
    assert engine.marking.scores[SCORE_ATROPHIC] == 2

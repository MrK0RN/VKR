from app.petri.engine import PetriEngine
from app.petri.model import PetriNet
from app.config import NET_JSON_PATH
from app.services.diagnosis import submit_section
from app.services.session_store import SessionData


def test_full_nodular_complaints_flow():
    net = PetriNet.from_json_path(NET_JSON_PATH)
    session = SessionData(session_id="test-1")
    answers = {pid: (pid == "b1") for pid in net.get_section("complaints").places}
    engine, tr, _ = submit_section(session, "complaints", answers)
    assert tr.nodular_fired
    assert engine.marking.places.get("b9") == 1
    assert engine.marking.scores["score_nodular"] == 2


def test_all_empty_sections():
    net = PetriNet.from_json_path(NET_JSON_PATH)
    session = SessionData(session_id="test-2")
    for section in net.sections:
        answers = {pid: False for pid in section.places}
        submit_section(session, section.id, answers)
    engine = PetriEngine(net)
    engine.rebuild_from_answers(session.answers)
    result = engine.finalize()
    assert result.score_nodular == 0
    assert result.score_mixed == 0

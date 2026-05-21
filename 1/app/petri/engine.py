from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.petri.model import PetriNet
from app.petri.net import Marking, TransitionResult


@dataclass
class Contribution:
    place_id: str
    label: str
    score_nodular: float
    score_mixed: float


@dataclass
class DiagnosisResult:
    score_nodular: float
    score_mixed: float
    winner: str | None
    winner_label: str | None
    tie: bool
    contributions: list[Contribution]
    marked_places: dict[str, bool]
    intermediate_marked: list[str]
    instrumental_transition_fired: bool


class PetriEngine:
    SCORE_NODULAR = "score_nodular"
    SCORE_MIXED = "score_mixed"

    def __init__(self, net: PetriNet, marking: Marking | None = None):
        self.net = net
        self.marking = marking or Marking()
        self.answers: dict[str, bool] = {}

    def get_marking(self) -> Marking:
        return self.marking

    def set_answers(self, answers: dict[str, bool]) -> None:
        self.answers = dict(answers)

    def rebuild_from_answers(self, answers: dict[str, bool]) -> None:
        self.answers = dict(answers)
        self.marking = Marking()
        for place_id, value in answers.items():
            if value:
                self._mark_place(place_id)

    def apply_user_input(self, place_id: str, value: bool) -> list[dict[str, Any]]:
        self.answers[place_id] = value
        if not value:
            return self._unmark_place(place_id)
        return self._mark_place(place_id)

    def _mark_place(self, place_id: str) -> list[dict[str, Any]]:
        place = self.net.places.get(place_id)
        if not place or place.place_type == "diagnosis_output":
            return []

        if place.exclusive_group:
            for pid, p in self.net.places.items():
                if p.exclusive_group == place.exclusive_group and pid != place_id:
                    self._unmark_place(pid)

        self.marking.places[place_id] = 1
        applied: list[dict[str, Any]] = []
        for arc in place.arcs:
            self.marking.scores[arc.target] = self.marking.scores.get(arc.target, 0) + arc.weight
            applied.append({"target": arc.target, "weight": arc.weight})
        return applied

    def _unmark_place(self, place_id: str) -> list[dict[str, Any]]:
        place = self.net.places.get(place_id)
        if not place or place_id not in self.marking.places:
            self.answers.pop(place_id, None)
            return []

        del self.marking.places[place_id]
        self.answers[place_id] = False
        for arc in place.arcs:
            self.marking.scores[arc.target] = max(
                0.0, self.marking.scores.get(arc.target, 0) - arc.weight
            )
        return []

    def _section_branch_weights(self, section_id: str) -> tuple[float, float]:
        nodular = 0.0
        mixed = 0.0
        section = self.net.get_section(section_id)
        if not section:
            return nodular, mixed
        for pid in section.places:
            if not self.answers.get(pid):
                continue
            place = self.net.places.get(pid)
            if not place:
                continue
            for arc in place.arcs:
                if arc.target == self.SCORE_NODULAR:
                    nodular += arc.weight
                elif arc.target == self.SCORE_MIXED:
                    mixed += arc.weight
        return nodular, mixed

    def evaluate_section_transition(self, section_id: str) -> TransitionResult:
        transition = self.net.transition_for_section(section_id)
        if not transition:
            return TransitionResult(fired=False, transition_id=None)

        nodular_fired = False
        mixed_fired = False

        if transition.fire_condition == "any_one_marked":
            any_marked = any(self.answers.get(pid) for pid in transition.input_places)
            if any_marked:
                nodular_fired = mixed_fired = True
                for key, place_id in transition.intermediate_on_fire.items():
                    if "nodular" in key:
                        self.marking.places[place_id] = 1
                    elif "mixed" in key:
                        self.marking.places[place_id] = 1
            fired = any_marked
        else:
            nodular_w, mixed_w = self._section_branch_weights(section_id)
            nodular_fired = nodular_w > 0
            mixed_fired = mixed_w > 0
            if nodular_fired and "nodular_branch" in transition.intermediate_on_fire:
                self.marking.places[transition.intermediate_on_fire["nodular_branch"]] = 1
            if mixed_fired and "mixed_branch" in transition.intermediate_on_fire:
                self.marking.places[transition.intermediate_on_fire["mixed_branch"]] = 1
            fired = nodular_fired or mixed_fired

        warning = None
        if not fired and transition.warning_message:
            warning = transition.warning_message

        return TransitionResult(
            fired=fired,
            nodular_fired=nodular_fired,
            mixed_fired=mixed_fired,
            warning_message=warning,
            transition_id=transition.id,
        )

    def finalize(self) -> DiagnosisResult:
        forms = self.net.meta.get("forms", {})
        nodular_key = forms.get("nodular", {}).get("score_key", self.SCORE_NODULAR)
        mixed_key = forms.get("mixed", {}).get("score_key", self.SCORE_MIXED)
        score_n = self.marking.scores.get(nodular_key, 0.0)
        score_m = self.marking.scores.get(mixed_key, 0.0)

        tie = score_n == score_m
        winner = None
        winner_label = None
        if not tie:
            if score_n > score_m:
                winner = "nodular"
                winner_label = forms.get("nodular", {}).get("label", "Нодулярный склероз")
            else:
                winner = "mixed"
                winner_label = forms.get("mixed", {}).get("label", "Смешанно-клеточный склероз")
        elif score_n > 0:
            winner_label = "Формы равновероятны по баллам"

        instrumental = self.net.transition_for_section("instrumental")
        inst_fired = False
        if instrumental:
            inst_fired = any(self.answers.get(pid) for pid in instrumental.input_places)

        return DiagnosisResult(
            score_nodular=score_n,
            score_mixed=score_m,
            winner=winner,
            winner_label=winner_label,
            tie=tie,
            contributions=self.explain(),
            marked_places=dict(self.answers),
            intermediate_marked=[
                pid for pid in self.net.intermediate_places if self.marking.places.get(pid)
            ],
            instrumental_transition_fired=inst_fired,
        )

    def explain(self) -> list[Contribution]:
        items: list[Contribution] = []
        for pid, marked in self.answers.items():
            if not marked:
                continue
            place = self.net.places.get(pid)
            if not place or not place.arcs:
                continue
            n = sum(a.weight for a in place.arcs if a.target == self.SCORE_NODULAR)
            m = sum(a.weight for a in place.arcs if a.target == self.SCORE_MIXED)
            if n or m:
                items.append(Contribution(place_id=pid, label=place.label, score_nodular=n, score_mixed=m))
        items.sort(key=lambda c: max(c.score_nodular, c.score_mixed), reverse=True)
        return items

    def to_state(self) -> dict[str, Any]:
        return {
            "answers": dict(self.answers),
            "marking": self.marking.to_dict(),
        }

    @classmethod
    def from_state(cls, net: PetriNet, state: dict[str, Any]) -> PetriEngine:
        engine = cls(net)
        answers = state.get("answers") or {}
        engine.rebuild_from_answers(answers)
        stored = state.get("marking")
        if stored and stored.get("places"):
            for pid, tok in stored["places"].items():
                if pid in net.intermediate_places:
                    engine.marking.places[pid] = tok
        return engine

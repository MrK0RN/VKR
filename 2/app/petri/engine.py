from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.petri.model import PetriNet
from app.petri.net import (
    SCORE_ATROPHIC,
    SCORE_HYPER,
    Marking,
    SectionResult,
    TransitionResult,
)


@dataclass
class DiagnosisResult:
    scores: dict[str, float]
    winner: str | None
    winner_label: str | None
    tie: bool
    hyper_label: str
    atrophic_label: str
    explain_hyper: list[dict[str, Any]] = field(default_factory=list)
    explain_atrophic: list[dict[str, Any]] = field(default_factory=list)


class PetriEngine:
    """Интерпретатор сети Петри: веса и переходы только из JSON."""

    def __init__(self, net: PetriNet):
        self.net = net
        self.marking = Marking()
        self.answers: dict[str, bool] = {}
        forms = net.meta.get("forms", {})
        self._hyper_label = forms.get("hyper", {}).get("label", "Гипертрофическая форма ХАТ")
        self._atrophic_label = forms.get("atrophic", {}).get("label", "Атрофическая форма ХАТ")

    def recompute_from_answers(self, answers: dict[str, bool]) -> None:
        """Полный пересчёт маркировки (идемпотентность при повторном POST)."""
        self.answers = {k: bool(v) for k, v in answers.items()}
        self.marking = Marking()
        for place_id, marked in self.answers.items():
            if marked and place_id in self.net.places:
                self._apply_place_mark(place_id)

    def _apply_place_mark(self, place_id: str) -> None:
        place = self.net.places[place_id]
        self.marking.places[place_id] = 1
        for arc in place.arcs:
            self.marking.scores[arc.target] = self.marking.scores.get(arc.target, 0.0) + arc.weight

    def _weight_for_branch(self, place_id: str, branch: str) -> float:
        place = self.net.places.get(place_id)
        if not place:
            return 0.0
        score_key = SCORE_HYPER if branch == "hyper" else SCORE_ATROPHIC
        return sum(a.weight for a in place.arcs if a.target == score_key)

    def _section_branch_scores(self, section_id: str) -> dict[str, float]:
        section = self.net.get_section(section_id)
        if not section:
            return {"hyper": 0.0, "atrophic": 0.0}
        hyper = 0.0
        atrophic = 0.0
        for pid in section.places:
            if not self.answers.get(pid):
                continue
            hyper += self._weight_for_branch(pid, "hyper")
            atrophic += self._weight_for_branch(pid, "atrophic")
        return {"hyper": hyper, "atrophic": atrophic}

    def _set_intermediate_token(self, place_id: str) -> None:
        self.marking.places[place_id] = 1

    def evaluate_transition_for_section(self, section_id: str) -> TransitionResult:
        transition = self.net.transition_for_section(section_id)
        if not transition:
            return TransitionResult(fired=True, transition_id=None)

        branch_scores = self._section_branch_scores(section_id)
        hyper_fired = branch_scores["hyper"] > 0
        atrophic_fired = branch_scores["atrophic"] > 0
        intermediate_marked: list[str] = []

        if transition.fire_condition == "any_one_marked":
            any_marked = any(self.answers.get(p, False) for p in transition.input_places)
            fired = any_marked or (
                self.net.rules.get("empty_instrumental_still_finalize", True) and not any_marked
            )
            if hyper_fired:
                ip = transition.intermediate_on_fire.get("hyper_branch")
                if ip:
                    self._set_intermediate_token(ip)
                    intermediate_marked.append(ip)
            if atrophic_fired:
                ip = transition.intermediate_on_fire.get("atrophic_branch")
                if ip:
                    self._set_intermediate_token(ip)
                    intermediate_marked.append(ip)
            for op in transition.output_places:
                if hyper_fired and op == self.net.final_places.get("hyper"):
                    self._set_intermediate_token(op)
                    intermediate_marked.append(op)
                if atrophic_fired and op == self.net.final_places.get("atrophic"):
                    self._set_intermediate_token(op)
                    intermediate_marked.append(op)
            return TransitionResult(
                fired=fired,
                hyper_branch_fired=hyper_fired,
                atrophic_branch_fired=atrophic_fired,
                transition_id=transition.id,
                intermediate_marked=intermediate_marked,
            )

        if transition.aggregate_condition == "sum_weights_gt_zero":
            if hyper_fired:
                ip = transition.intermediate_on_fire.get("hyper_branch")
                if ip:
                    self._set_intermediate_token(ip)
                    intermediate_marked.append(ip)
            if atrophic_fired:
                ip = transition.intermediate_on_fire.get("atrophic_branch")
                if ip:
                    self._set_intermediate_token(ip)
                    intermediate_marked.append(ip)
            fired = hyper_fired or atrophic_fired
            warning = None if fired else transition.warning_message
            return TransitionResult(
                fired=fired,
                hyper_branch_fired=hyper_fired,
                atrophic_branch_fired=atrophic_fired,
                warning_message=warning,
                transition_id=transition.id,
                intermediate_marked=intermediate_marked,
            )

        return TransitionResult(fired=True, transition_id=transition.id)

    def apply_section(self, section_id: str, section_answers: dict[str, bool]) -> SectionResult:
        section = self.net.get_section(section_id)
        if not section:
            raise ValueError(f"Unknown section: {section_id}")

        merged = dict(self.answers)
        for pid in section.places:
            merged[pid] = bool(section_answers.get(pid, False))

        self._normalize_exclusive_groups(merged)
        self.recompute_from_answers(merged)
        tr = self.evaluate_transition_for_section(section_id)

        return SectionResult(
            scores=dict(self.marking.scores),
            transition_fired=tr.fired,
            warning=tr.warning_message,
            intermediate_marked=tr.intermediate_marked,
            marking=self.marking.to_dict(),
        )

    def _normalize_exclusive_groups(self, answers: dict[str, bool]) -> None:
        groups: dict[str, list[str]] = {}
        for pid, place in self.net.places.items():
            if place.exclusive_group:
                groups.setdefault(place.exclusive_group, []).append(pid)
        for group_places in groups.values():
            marked = [p for p in group_places if answers.get(p)]
            if len(marked) > 1:
                keep = marked[-1]
                for p in group_places:
                    answers[p] = p == keep

    def finalize(self) -> DiagnosisResult:
        hyper = self.marking.scores.get(SCORE_HYPER, 0.0)
        atrophic = self.marking.scores.get(SCORE_ATROPHIC, 0.0)
        tie = hyper == atrophic
        winner: str | None
        winner_label: str | None
        if tie:
            winner = None
            winner_label = None
        elif hyper > atrophic:
            winner = "hyper"
            winner_label = self._hyper_label
        else:
            winner = "atrophic"
            winner_label = self._atrophic_label

        return DiagnosisResult(
            scores=dict(self.marking.scores),
            winner=winner,
            winner_label=winner_label,
            tie=tie,
            hyper_label=self._hyper_label,
            atrophic_label=self._atrophic_label,
            explain_hyper=self._explain_branch(SCORE_HYPER),
            explain_atrophic=self._explain_branch(SCORE_ATROPHIC),
        )

    def _explain_branch(self, score_key: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for pid, marked in sorted(self.answers.items()):
            if not marked or pid not in self.net.places:
                continue
            place = self.net.places[pid]
            weight = sum(a.weight for a in place.arcs if a.target == score_key)
            if weight > 0:
                items.append({"place_id": pid, "label": place.label, "weight": weight})
        items.sort(key=lambda x: (-x["weight"], x["place_id"]))
        return items

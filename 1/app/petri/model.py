from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.petri.net import Arc, Place, Section, Transition


class PetriNet:
    def __init__(self, data: dict[str, Any]):
        self.meta = data.get("meta", {})
        self.rules = data.get("rules", {})
        self.final_places = data.get("final_places", {})
        self.intermediate_places: dict[str, dict] = data.get("intermediate_places", {})
        self.places: dict[str, Place] = {}
        self.transitions: dict[str, Transition] = {}
        self.sections: list[Section] = []
        self._load_places(data.get("places", {}))
        self._load_sections(data.get("sections", []))
        self._load_transitions(data.get("transitions", []))

    def _load_places(self, raw: dict[str, Any]) -> None:
        for pid, p in raw.items():
            arcs = [Arc(target=a["target"], weight=float(a["weight"])) for a in p.get("arcs", [])]
            self.places[pid] = Place(
                id=pid,
                label=p["label"],
                section=p.get("section", ""),
                input_type=p.get("input_type", "boolean"),
                show_threshold_hint=p.get("show_threshold_hint", True),
                arcs=arcs,
                exclusive_group=p.get("exclusive_group"),
                place_type=p.get("place_type"),
            )

    def _load_sections(self, raw: list[dict]) -> None:
        self.sections = sorted(
            [
                Section(
                    id=s["id"],
                    title=s["title"],
                    order=s["order"],
                    places=list(s["places"]),
                    intermediate_outputs=list(s.get("intermediate_outputs", [])),
                    intermediate_inputs=list(s.get("intermediate_inputs", [])),
                )
                for s in raw
            ],
            key=lambda x: x.order,
        )

    def _load_transitions(self, raw: list[dict]) -> None:
        for t in raw:
            warning = t.get("warning_if_no_tokens") or {}
            self.transitions[t["id"]] = Transition(
                id=t["id"],
                from_section=t["from_section"],
                to_section=t["to_section"],
                aggregate_condition=t.get("aggregate_condition"),
                fire_condition=t.get("fire_condition"),
                input_places=list(t.get("input_places", [])),
                intermediate_on_fire=dict(t.get("intermediate_on_fire", {})),
                output_places=list(t.get("output_places", [])),
                warning_message=warning.get("message"),
                min_branch_weights={
                    k: float(v) for k, v in (t.get("min_branch_weights") or {}).items()
                },
            )

    def get_section(self, section_id: str) -> Section | None:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None

    def get_section_by_order(self, order: int) -> Section | None:
        for s in self.sections:
            if s.order == order:
                return s
        return None

    def transition_for_section(self, section_id: str) -> Transition | None:
        for t in self.transitions.values():
            if t.from_section == section_id:
                return t
        return None

    @classmethod
    def from_json_path(cls, path: Path) -> PetriNet:
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Arc:
    target: str
    weight: float


@dataclass
class Place:
    id: str
    label: str
    section: str
    input_type: str = "boolean"
    show_threshold_hint: bool = True
    arcs: list[Arc] = field(default_factory=list)
    exclusive_group: str | None = None
    place_type: str | None = None


@dataclass
class Transition:
    id: str
    from_section: str
    to_section: str
    aggregate_condition: str | None = None
    fire_condition: str | None = None
    input_places: list[str] = field(default_factory=list)
    intermediate_on_fire: dict[str, str] = field(default_factory=dict)
    output_places: list[str] = field(default_factory=list)
    warning_message: str | None = None
    min_branch_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class Section:
    id: str
    title: str
    order: int
    places: list[str]
    intermediate_outputs: list[str] = field(default_factory=list)
    intermediate_inputs: list[str] = field(default_factory=list)


@dataclass
class Marking:
    places: dict[str, int] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=lambda: {
        "score_nodular": 0.0,
        "score_mixed": 0.0,
    })

    def to_dict(self) -> dict[str, Any]:
        return {"places": dict(self.places), "scores": dict(self.scores)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Marking:
        scores = data.get("scores") or {"score_nodular": 0.0, "score_mixed": 0.0}
        return cls(
            places=dict(data.get("places") or {}),
            scores={
                "score_nodular": float(scores.get("score_nodular", 0)),
                "score_mixed": float(scores.get("score_mixed", 0)),
            },
        )


@dataclass
class TransitionResult:
    fired: bool
    nodular_fired: bool = False
    mixed_fired: bool = False
    warning_message: str | None = None
    transition_id: str | None = None

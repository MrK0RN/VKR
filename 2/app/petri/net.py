from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCORE_HYPER = "score_hyper"
SCORE_ATROPHIC = "score_atrophic"
DEFAULT_SCORES = {SCORE_HYPER: 0.0, SCORE_ATROPHIC: 0.0}


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
    arcs: list[Arc] = field(default_factory=list)
    exclusive_group: str | None = None
    place_type: str | None = None
    laboratory_branch: str | None = None


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


@dataclass
class Section:
    id: str
    title: str
    order: int
    places: list[str]
    intermediate_outputs: list[str] = field(default_factory=list)
    intermediate_inputs: list[str] = field(default_factory=list)
    laboratory_groups: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Marking:
    places: dict[str, int] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCORES))

    def to_dict(self) -> dict[str, Any]:
        return {"places": dict(self.places), "scores": dict(self.scores)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Marking:
        scores = data.get("scores") or dict(DEFAULT_SCORES)
        return cls(
            places=dict(data.get("places") or {}),
            scores={
                SCORE_HYPER: float(scores.get(SCORE_HYPER, 0)),
                SCORE_ATROPHIC: float(scores.get(SCORE_ATROPHIC, 0)),
            },
        )


@dataclass
class TransitionResult:
    fired: bool
    hyper_branch_fired: bool = False
    atrophic_branch_fired: bool = False
    warning_message: str | None = None
    transition_id: str | None = None
    intermediate_marked: list[str] = field(default_factory=list)


@dataclass
class SectionResult:
    scores: dict[str, float]
    transition_fired: bool
    warning: str | None
    intermediate_marked: list[str]
    marking: dict[str, Any]

"""Schemas and data models for Module 3: Opponent Move Prediction.

Defines structured models for opponent responses, candidate consequences,
tactical threats, evaluation scores, and search metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.chess_engine.models import PieceColor
from backend.predictor.schemas import EvaluationScore, ScoreType


class PredictionType(str, Enum):
    """Categorization of move prediction methodology."""

    ADVERSARIAL_MINIMAX = "adversarial_minimax"
    STATISTICAL_HUMAN = "statistical_human"


class SearchStatus(str, Enum):
    """Outcome status of an opponent search iteration."""

    COMPLETED = "completed"
    TIMEOUT_INTERRUPTED = "timeout_interrupted"
    TERMINAL = "terminal"


@dataclass
class OpponentResponse:
    """The predicted optimal opponent reply to a played candidate move."""

    move_uci: Optional[str]
    move_san: Optional[str]
    evaluation: EvaluationScore
    pv_uci: List[str]
    pv_san: List[str]
    is_forced_mate: bool
    mate_in: Optional[int]
    is_check: bool = False
    is_capture: bool = False
    tactical_threat: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert opponent response to dictionary representation."""
        return {
            "move_uci": self.move_uci,
            "move_san": self.move_san,
            "evaluation": self.evaluation.to_dict(),
            "pv_uci": list(self.pv_uci),
            "pv_san": list(self.pv_san),
            "is_forced_mate": self.is_forced_mate,
            "mate_in": self.mate_in,
            "is_check": self.is_check,
            "is_capture": self.is_capture,
            "tactical_threat": self.tactical_threat,
        }


@dataclass
class CandidateConsequence:
    """Detailed adversarial analysis of playing a specific candidate move."""

    candidate_move_uci: str
    candidate_move_san: str
    predicted_opponent_response: Optional[OpponentResponse]
    post_candidate_evaluation: EvaluationScore
    pv_uci: List[str]
    pv_san: List[str]
    search_depth: int
    nodes_evaluated: int
    search_duration_ms: float
    is_forced_mate: bool
    mate_in: Optional[int]
    status: SearchStatus
    material_delta: int = 0
    prediction_type: PredictionType = PredictionType.ADVERSARIAL_MINIMAX

    def to_dict(self) -> Dict[str, Any]:
        """Convert candidate consequence to a JSON-serializable dictionary."""
        return {
            "candidate_move": {
                "uci": self.candidate_move_uci,
                "san": self.candidate_move_san,
            },
            "predicted_opponent_response": (
                self.predicted_opponent_response.to_dict()
                if self.predicted_opponent_response
                else None
            ),
            "post_candidate_evaluation": self.post_candidate_evaluation.to_dict(),
            "pv_uci": list(self.pv_uci),
            "pv_san": list(self.pv_san),
            "search_depth": self.search_depth,
            "nodes_evaluated": self.nodes_evaluated,
            "search_duration_ms": round(self.search_duration_ms, 2),
            "is_forced_mate": self.is_forced_mate,
            "mate_in": self.mate_in,
            "status": self.status.value,
            "material_delta": self.material_delta,
            "prediction_type": self.prediction_type.value,
        }


@dataclass
class OpponentAnalysisReport:
    """Complete report analyzing opponent responses across multiple candidate moves."""

    fen: str
    side_to_move: PieceColor
    opponent_side: PieceColor
    consequences: List[CandidateConsequence]
    best_candidate_uci: Optional[str]
    best_candidate_san: Optional[str]
    total_nodes: int
    total_duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert full report to dictionary representation."""
        return {
            "fen": self.fen,
            "side_to_move": self.side_to_move.value,
            "opponent_side": self.opponent_side.value,
            "best_candidate": {
                "uci": self.best_candidate_uci,
                "san": self.best_candidate_san,
            }
            if self.best_candidate_uci
            else None,
            "candidate_consequences": [c.to_dict() for c in self.consequences],
            "total_nodes": self.total_nodes,
            "total_duration_ms": round(self.total_duration_ms, 2),
        }

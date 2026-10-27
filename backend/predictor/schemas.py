"""Schemas and data models for Module 2: Best Move Predictor.

Defines structured representations for candidate moves, evaluation scores,
principal variations, analysis parameters, and engine status codes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.chess_engine.models import PieceColor


class ScoreType(str, Enum):
    """Evaluation score type: centipawns or mate."""

    CENTIPAWN = "cp"
    MATE = "mate"


class EngineStatus(str, Enum):
    """Execution status of the analysis engine."""

    OK = "ok"
    TERMINAL_POSITION = "terminal_position"
    NOT_AVAILABLE = "not_available"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class EvaluationScore:
    """Detailed chess evaluation score with perspective normalization."""

    score_type: ScoreType
    value: int
    score_relative_cp: Optional[int] = None
    score_white_cp: Optional[int] = None
    mate_in_relative: Optional[int] = None
    mate_in_white: Optional[int] = None
    display_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert evaluation score to dictionary."""
        return {
            "score_type": self.score_type.value,
            "value": self.value,
            "score_relative_cp": self.score_relative_cp,
            "score_white_cp": self.score_white_cp,
            "mate_in_relative": self.mate_in_relative,
            "mate_in_white": self.mate_in_white,
            "display_text": self.display_text,
        }


@dataclass
class MoveCandidate:
    """Ranked candidate move with evaluation and principal variation continuation."""

    rank: int
    uci: str
    san: str
    evaluation: EvaluationScore
    pv_uci: List[str]
    pv_san: List[str]
    is_best_move: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert move candidate to dictionary representation."""
        return {
            "rank": self.rank,
            "uci": self.uci,
            "san": self.san,
            "is_best_move": self.is_best_move,
            "evaluation": self.evaluation.to_dict(),
            "pv_uci": list(self.pv_uci),
            "pv_san": list(self.pv_san),
        }


@dataclass
class AnalysisResult:
    """Complete structured response from a position evaluation analysis."""

    fen: str
    side_to_move: PieceColor
    best_move_uci: Optional[str]
    best_move_san: Optional[str]
    candidates: List[MoveCandidate]
    search_depth: int
    analysis_time_ms: float
    engine_status: EngineStatus
    engine_name: str
    nodes_evaluated: Optional[int] = None
    is_terminal: bool = False
    terminal_reason: Optional[str] = None
    disclaimer: str = (
        "Depth-limited heuristic evaluation. Not a mathematically guaranteed optimal move."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to a JSON-serializable dictionary."""
        return {
            "fen": self.fen,
            "side_to_move": self.side_to_move.value,
            "best_move": {
                "uci": self.best_move_uci,
                "san": self.best_move_san,
            }
            if self.best_move_uci
            else None,
            "candidate_moves": [c.to_dict() for c in self.candidates],
            "search_depth": self.search_depth,
            "analysis_time_ms": round(self.analysis_time_ms, 2),
            "engine_status": self.engine_status.value,
            "engine_name": self.engine_name,
            "nodes_evaluated": self.nodes_evaluated,
            "is_terminal": self.is_terminal,
            "terminal_reason": self.terminal_reason,
            "disclaimer": self.disclaimer,
        }


@dataclass
class ComparisonResult:
    """Side-by-side comparison between Stockfish and Minimax search engines."""

    fen: str
    side_to_move: PieceColor
    stockfish_analysis: Optional[AnalysisResult]
    minimax_analysis: AnalysisResult
    agreement: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert comparison result to a dictionary representation."""
        return {
            "fen": self.fen,
            "side_to_move": self.side_to_move.value,
            "agreement": self.agreement,
            "summary": self.summary,
            "stockfish": self.stockfish_analysis.to_dict()
            if self.stockfish_analysis
            else None,
            "minimax": self.minimax_analysis.to_dict(),
        }

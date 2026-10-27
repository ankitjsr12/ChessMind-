"""Module 3: Opponent Move Prediction for ChessMind AI.

Exposes OpponentSearchEngine, PositionEvaluator, MoveOrderer, TranspositionTable,
and schemas for opponent response prediction.
"""

from backend.opponent_prediction.evaluation import (
    EvaluationBreakdown,
    PositionEvaluator,
)
from backend.opponent_prediction.move_ordering import MoveOrderer
from backend.opponent_prediction.schemas import (
    CandidateConsequence,
    OpponentAnalysisReport,
    OpponentResponse,
    PredictionType,
    SearchStatus,
)
from backend.opponent_prediction.search import OpponentSearchEngine
from backend.opponent_prediction.transposition_table import (
    TTFlag,
    TranspositionTable,
)

__all__ = [
    "OpponentSearchEngine",
    "PositionEvaluator",
    "EvaluationBreakdown",
    "MoveOrderer",
    "TranspositionTable",
    "TTFlag",
    "CandidateConsequence",
    "OpponentAnalysisReport",
    "OpponentResponse",
    "PredictionType",
    "SearchStatus",
]

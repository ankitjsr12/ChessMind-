"""Chess Engine Module for ChessMind AI.

Exposes the primary ChessEngine class, models, and custom exceptions.
"""

from backend.chess_engine.engine import ChessEngine
from backend.chess_engine.exceptions import (
    ChessEngineException,
    GameOverError,
    IllegalMoveError,
    InvalidFENError,
    InvalidMoveError,
    InvalidPGNError,
    NoMovesToUndoError,
)
from backend.chess_engine.models import (
    BaseMovePredictor,
    BoardState,
    CastlingRights,
    GameResult,
    GameTermination,
    MoveRecord,
    MoveResult,
    PieceColor,
    PieceType,
    TerminationReason,
)

__all__ = [
    "ChessEngine",
    "BaseMovePredictor",
    "BoardState",
    "CastlingRights",
    "GameResult",
    "GameTermination",
    "MoveRecord",
    "MoveResult",
    "PieceColor",
    "PieceType",
    "TerminationReason",
    "ChessEngineException",
    "GameOverError",
    "IllegalMoveError",
    "InvalidFENError",
    "InvalidMoveError",
    "InvalidPGNError",
    "NoMovesToUndoError",
]

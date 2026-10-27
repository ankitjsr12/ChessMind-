"""Data models and value objects for the Chess Engine module.

This module encapsulates board states, move representations, castling rights,
game outcomes, and AI predictor protocols using typed dataclasses and enums.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
import chess


class PieceColor(str, Enum):
    """Represents player and piece colors."""

    WHITE = "white"
    BLACK = "black"

    @property
    def opposite(self) -> PieceColor:
        """Return the opposing color."""
        return PieceColor.BLACK if self == PieceColor.WHITE else PieceColor.WHITE

    @classmethod
    def from_chess(cls, color: chess.Color) -> PieceColor:
        """Convert a python-chess Color boolean to PieceColor."""
        return cls.WHITE if color == chess.WHITE else cls.BLACK


class PieceType(str, Enum):
    """Standard chess piece types."""

    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


class GameResult(str, Enum):
    """Standard chess game result codes."""

    WHITE_WINS = "1-0"
    BLACK_WINS = "0-1"
    DRAW = "1/2-1/2"
    IN_PROGRESS = "*"


class TerminationReason(str, Enum):
    """Reason why a chess game concluded."""

    NOT_TERMINATED = "not_terminated"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVES = "fifty_moves"
    FIVEFOLD_REPETITION = "fivefold_repetition"
    SEVENTYFIVE_MOVES = "seventyfive_moves"
    RESIGNATION = "resignation"


@dataclass(frozen=True)
class CastlingRights:
    """Castling rights for both white and black sides."""

    white_kingside: bool
    white_queenside: bool
    black_kingside: bool
    black_queenside: bool

    def to_dict(self) -> Dict[str, bool]:
        """Convert castling rights to a dictionary."""
        return asdict(self)


@dataclass
class MoveRecord:
    """Detailed record of a single executed chess move."""

    move_number: int
    uci: str
    san: str
    turn: PieceColor
    fen_before: str
    fen_after: str
    piece_moved: str
    captured_piece: Optional[str] = None
    is_capture: bool = False
    is_check: bool = False
    is_checkmate: bool = False
    is_castling: bool = False
    is_en_passant: bool = False
    is_promotion: bool = False
    promotion_piece: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert move record to a dictionary."""
        data = asdict(self)
        data["turn"] = self.turn.value
        return data


@dataclass
class GameTermination:
    """Encapsulates the terminal state and verdict of a game."""

    is_terminated: bool
    winner: Optional[PieceColor]
    result_code: GameResult
    reason: TerminationReason
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert termination information to a dictionary."""
        return {
            "is_terminated": self.is_terminated,
            "winner": self.winner.value if self.winner else None,
            "result_code": self.result_code.value,
            "reason": self.reason.value,
            "description": self.description,
        }


@dataclass
class BoardState:
    """Comprehensive snapshot of the chess board at any point in time."""

    fen: str
    turn: PieceColor
    fullmove_number: int
    halfmove_clock: int
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    is_insufficient_material: bool
    is_fivefold_repetition: bool
    is_seventyfive_moves: bool
    can_claim_draw: bool
    can_claim_threefold_repetition: bool
    can_claim_fifty_moves: bool
    is_game_over: bool
    draw_reason: Optional[str]
    legal_moves_uci: List[str]
    legal_moves_san: List[str]
    castling_rights: CastlingRights
    en_passant_square: Optional[str]
    board_matrix: List[List[Optional[str]]]
    piece_counts: Dict[str, int]
    captured_pieces: Dict[str, List[str]] = field(
        default_factory=lambda: {"white": [], "black": []}
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert board state to a dictionary representation."""
        return {
            "fen": self.fen,
            "turn": self.turn.value,
            "fullmove_number": self.fullmove_number,
            "halfmove_clock": self.halfmove_clock,
            "is_check": self.is_check,
            "is_checkmate": self.is_checkmate,
            "is_stalemate": self.is_stalemate,
            "is_insufficient_material": self.is_insufficient_material,
            "is_fivefold_repetition": self.is_fivefold_repetition,
            "is_seventyfive_moves": self.is_seventyfive_moves,
            "can_claim_draw": self.can_claim_draw,
            "can_claim_threefold_repetition": self.can_claim_threefold_repetition,
            "can_claim_fifty_moves": self.can_claim_fifty_moves,
            "is_game_over": self.is_game_over,
            "draw_reason": self.draw_reason,
            "legal_moves_uci": list(self.legal_moves_uci),
            "legal_moves_san": list(self.legal_moves_san),
            "castling_rights": self.castling_rights.to_dict(),
            "en_passant_square": self.en_passant_square,
            "board_matrix": self.board_matrix,
            "piece_counts": self.piece_counts,
            "captured_pieces": self.captured_pieces,
        }


@dataclass
class MoveResult:
    """Result returned immediately following move execution."""

    move_record: MoveRecord
    board_state: BoardState
    termination: GameTermination

    def to_dict(self) -> Dict[str, Any]:
        """Convert move result to dictionary."""
        return {
            "move": self.move_record.to_dict(),
            "board_state": self.board_state.to_dict(),
            "termination": self.termination.to_dict(),
        }


@runtime_checkable
class BaseMovePredictor(Protocol):
    """Protocol for pluggable AI, ML, Deep Learning, and Stockfish predictors.

    Future modules (e.g. Heuristic Bot, Stockfish, ML Evaluator, Deep Neural Net)
    can implement this protocol to be seamlessly used with ChessEngine.play_ai_move().
    """

    def predict_move(self, fen: str, legal_moves_uci: List[str]) -> Optional[str]:
        """Predict the best or next move given the current FEN and legal UCI moves.

        Args:
            fen: The board position in FEN notation.
            legal_moves_uci: List of legal moves in UCI format.

        Returns:
            A legal UCI move string (e.g., 'e2e4'), or None if unable to predict.
        """
        ...

"""Custom exceptions for the Chess Engine module.

This module defines clear, domain-specific exceptions for chess move validation,
FEN parsing, PGN import/export, and game state transitions.
"""

from typing import Optional


class ChessEngineException(Exception):
    """Base exception for all chess engine related errors."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class InvalidMoveError(ChessEngineException):
    """Raised when a move string cannot be parsed or has invalid syntax.

    Example: 'e9e5', 'invalid_str', or malformed SAN notation.
    """

    def __init__(self, move_str: str, reason: str = "Malformed move syntax") -> None:
        super().__init__(
            f"Invalid move '{move_str}': {reason}",
            details={"move": move_str, "reason": reason},
        )
        self.move_str = move_str
        self.reason = reason


class IllegalMoveError(ChessEngineException):
    """Raised when a syntactically valid move violates the rules of chess in the current position.

    Example: Moving a piece through another piece, moving into check, or moving opponent's piece.
    """

    def __init__(
        self,
        move_str: str,
        fen: Optional[str] = None,
        reason: str = "Move is not legal in current position",
    ) -> None:
        details = {"move": move_str, "reason": reason}
        if fen:
            details["fen"] = fen
        super().__init__(
            f"Illegal move '{move_str}': {reason}",
            details=details,
        )
        self.move_str = move_str
        self.fen = fen
        self.reason = reason


class InvalidFENError(ChessEngineException):
    """Raised when initializing or loading an invalid FEN string."""

    def __init__(self, fen: str, reason: str = "Malformed or illegal FEN string") -> None:
        super().__init__(
            f"Invalid FEN '{fen}': {reason}",
            details={"fen": fen, "reason": reason},
        )
        self.fen = fen
        self.reason = reason


class InvalidPGNError(ChessEngineException):
    """Raised when parsing or importing an invalid PGN format."""

    def __init__(self, pgn_str: str, reason: str = "Failed to parse PGN data") -> None:
        preview = pgn_str[:80] + "..." if len(pgn_str) > 80 else pgn_str
        super().__init__(
            f"Invalid PGN: {reason}. Content preview: {preview!r}",
            details={"reason": reason, "pgn_preview": preview},
        )
        self.pgn_str = pgn_str
        self.reason = reason


class GameOverError(ChessEngineException):
    """Raised when attempting to execute a move after the game has already concluded."""

    def __init__(self, result: str, reason: str) -> None:
        super().__init__(
            f"Cannot make move: Game is already over ({reason}, result: {result})",
            details={"result": result, "reason": reason},
        )
        self.result = result
        self.reason = reason


class NoMovesToUndoError(ChessEngineException):
    """Raised when attempting to undo a move on an empty move history."""

    def __init__(self, message: str = "No moves available in history to undo") -> None:
        super().__init__(message)

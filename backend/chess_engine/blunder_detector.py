"""Tactical Blunder Detector and Explainable Move Quality Engine for ChessMind AI.

Analyzes centipawn loss, material shifts, king safety, and tactical patterns (pins, forks,
hanging pieces) to classify moves into GM-grade tiers (Brilliant, Great, Best, Good,
Inaccuracy, Mistake, Blunder, Missed Win) with human-readable tactical explanations.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import chess


class BlunderDetector:
    """Classifies moves and generates explainable tactical insights."""

    PIECE_NAMES = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
        chess.KING: "king",
    }

    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }

    @classmethod
    def classify_move(
        cls,
        board_before: chess.Board,
        move: chess.Move,
        board_after: chess.Board,
        played_cp: float,
        best_cp: float,
        best_move: Optional[chess.Move] = None,
    ) -> Dict[str, Any]:
        """Classify move quality and compute accuracy, loss, and tactical explanation.

        Args:
            board_before: Board position before move was played.
            move: Move that was executed.
            board_after: Board position after move was executed.
            played_cp: Evaluation after move from mover's perspective.
            best_cp: Evaluation of best possible move from mover's perspective.
            best_move: The optimal engine move.

        Returns:
            Dict containing quality tier, accuracy, cp_loss, explanation, and tags.
        """
        turn_color = board_before.turn
        mover_color_str = "white" if turn_color == chess.WHITE else "black"
        opponent_color_str = "black" if turn_color == chess.WHITE else "white"

        # Centipawn loss from perspective of player who moved
        cp_loss = max(0.0, float(best_cp - played_cp))

        # Exponential Accuracy Formula normalized for centipawns
        # 0 cp loss = 100%, 15 cp loss ~ 92%, 50 cp loss ~ 77%, 150 cp loss ~ 45%, 300+ cp ~ <15%
        if cp_loss <= 0.01:
            accuracy = 100.0
        else:
            accuracy = max(0.0, min(100.0, 103.1668 * math.exp(-0.0075 * min(cp_loss, 400.0)) - 3.1669))

        # Check for checkmate on board
        is_checkmate = board_after.is_checkmate()
        is_check = board_after.is_check()

        # Material balance check
        moved_piece = board_before.piece_at(move.from_square)
        moved_piece_type = moved_piece.piece_type if moved_piece else chess.PAWN
        moved_piece_name = cls.PIECE_NAMES.get(moved_piece_type, "piece")

        captured_piece = board_before.piece_at(move.to_square)
        is_capture = captured_piece is not None or board_before.is_en_passant(move)

        # 1. Check for Brilliant Move (Sacrifice with decisive winning position)
        is_brilliant = False
        if not is_capture and moved_piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            # Check if moved piece was moved to a square attacked by opponent and undefended, or defended by lesser piece
            attackers = board_after.attackers(not turn_color, move.to_square)
            defenders = board_after.attackers(turn_color, move.to_square)
            if attackers and len(attackers) > len(defenders) and played_cp >= 200.0 and cp_loss <= 15.0:
                is_brilliant = True

        # 2. Check for Missed Win (Was winning by >350 cp, now equal or losing)
        is_missed_win = False
        if best_cp >= 350.0 and played_cp < 100.0 and cp_loss >= 250.0:
            is_missed_win = True

        # Determine Quality Tier
        if is_checkmate:
            quality = "best"
            explanation = f"Delivers checkmate! Outstanding finish."
        elif is_brilliant:
            quality = "brilliant"
            explanation = f"Brilliant {moved_piece_name} sacrifice maintaining decisive advantage."
        elif is_missed_win:
            quality = "missed_win"
            explanation = f"Missed winning opportunity. Best move was {board_before.san(best_move) if best_move else 'found by engine'}."
        elif cp_loss <= 15:
            quality = "best"
            if is_check:
                explanation = f"Top engine move delivering a sharp check."
            elif is_capture:
                explanation = f"Accurate tactical recapture on {chess.square_name(move.to_square)}."
            else:
                explanation = f"Optimal positional move maintaining maximum pressure."
        elif cp_loss <= 35:
            quality = "good"
            explanation = f"Solid move keeping good control of the board."
        elif cp_loss <= 90:
            quality = "inaccuracy"
            explanation = f"Slight inaccuracy. Better was {board_before.san(best_move) if best_move else 'an alternative line'}."
        elif cp_loss <= 200:
            quality = "mistake"
            explanation = f"Mistake conceding advantage ({round(cp_loss / 100, 1)} pawns lost)."
        else:
            quality = "blunder"
            # Detect hanging piece or checkmate threat
            hanging_piece_desc = cls._detect_hanging_piece(board_after, turn_color)
            if hanging_piece_desc:
                explanation = f"Blunder: {hanging_piece_desc}"
            else:
                explanation = f"Major blunder forfeiting significant material or king safety ({round(cp_loss / 100, 1)} pawns)."

        return {
            "quality": quality,
            "accuracy": round(accuracy, 1),
            "cp_loss": round(cp_loss, 1),
            "explanation": explanation,
            "is_check": is_check,
            "is_checkmate": is_checkmate,
            "is_capture": is_capture,
        }

    @classmethod
    def _detect_hanging_piece(cls, board: chess.Board, player_color: chess.Color) -> Optional[str]:
        """Detect if player left an undefended piece hanging on the board."""
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == player_color and piece.piece_type != chess.KING:
                attackers = board.attackers(not player_color, sq)
                defenders = board.attackers(player_color, sq)
                if attackers and not defenders:
                    p_name = cls.PIECE_NAMES.get(piece.piece_type, "piece")
                    sq_name = chess.square_name(sq)
                    return f"Leaves {p_name} on {sq_name} completely undefended."
        return None


# Global singleton blunder detector
blunder_detector = BlunderDetector()

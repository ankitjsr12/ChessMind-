"""Evaluation function for Module 3: Opponent Move Prediction.

Combines:
- Material balance with bishop-pair bonus
- Piece-Square Tables (PST) with game-phase interpolation
- Piece mobility (legal attack counts)
- King safety (pawn shield, open files near king, enemy queen threat)
- Pawn structure (doubled pawns, isolated pawns, passed pawn advancement)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import chess

PIECE_VALUES: Dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

BISHOP_PAIR_BONUS = 30
DOUBLED_PAWN_PENALTY = 15
ISOLATED_PAWN_PENALTY = 20

# Passed pawn bonuses by rank (indexed 0 to 7, ranks 1 to 8)
PASSED_PAWN_BONUS = [0, 10, 15, 25, 40, 65, 110, 0]

# Piece-Square Tables (oriented for White, mirrored vertically for Black)
PAWN_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5,  5, 10, 25, 25, 10,  5,  5,
    0,  0,  0, 20, 20,  0,  0,  0,
    5, -5,-10,  0,  0,-10, -5,  5,
    5, 10, 10,-20,-20, 10, 10,  5,
    0,  0,  0,  0,  0,  0,  0,  0
]

KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]

BISHOP_TABLE = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]

ROOK_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
    5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    0,  0,  0,  5,  5,  0,  0,  0
]

QUEEN_TABLE = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
    0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]

KING_TABLE_MIDGAME = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20
]

KING_TABLE_ENDGAME = [
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
]

PST_MAP = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
}


@dataclass
class EvaluationBreakdown:
    """Detailed decomposition of static evaluation components."""

    total: int
    material_white: int
    material_black: int
    pst_white: int
    pst_black: int
    mobility_white: int
    mobility_black: int
    king_safety_white: int
    king_safety_black: int
    pawn_structure_white: int
    pawn_structure_black: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert breakdown to dictionary."""
        return {
            "total_score": self.total,
            "material": {"white": self.material_white, "black": self.material_black},
            "pst": {"white": self.pst_white, "black": self.pst_black},
            "mobility": {"white": self.mobility_white, "black": self.mobility_black},
            "king_safety": {"white": self.king_safety_white, "black": self.king_safety_black},
            "pawn_structure": {
                "white": self.pawn_structure_white,
                "black": self.pawn_structure_black,
            },
        }


class PositionEvaluator:
    """Evaluates chess positions considering material, PST, mobility, king safety, and pawns."""

    @classmethod
    def _compute_phase(cls, board: chess.Board) -> float:
        """Compute game phase factor (1.0 = midgame, 0.0 = endgame)."""
        # Maximum non-pawn material: 4 Knights, 4 Bishops, 4 Rooks, 2 Queens
        # Weights: Knight=1, Bishop=1, Rook=2, Queen=4 => Total phase = 24
        phase = (
            len(board.pieces(chess.KNIGHT, chess.WHITE)) * 1
            + len(board.pieces(chess.KNIGHT, chess.BLACK)) * 1
            + len(board.pieces(chess.BISHOP, chess.WHITE)) * 1
            + len(board.pieces(chess.BISHOP, chess.BLACK)) * 1
            + len(board.pieces(chess.ROOK, chess.WHITE)) * 2
            + len(board.pieces(chess.ROOK, chess.BLACK)) * 2
            + len(board.pieces(chess.QUEEN, chess.WHITE)) * 4
            + len(board.pieces(chess.QUEEN, chess.BLACK)) * 4
        )
        return min(max(phase / 24.0, 0.0), 1.0)

    @classmethod
    def _evaluate_pawn_structure(cls, board: chess.Board, color: chess.Color) -> int:
        """Evaluate doubled, isolated, and passed pawns for a given side."""
        score = 0
        pawns = board.pieces(chess.PAWN, color)
        enemy_pawns = board.pieces(chess.PAWN, not color)

        # Count pawns per file (files 0 to 7)
        file_counts = [0] * 8
        for sq in pawns:
            f = chess.square_file(sq)
            file_counts[f] += 1

        for sq in pawns:
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)

            # 1. Doubled pawns penalty
            if file_counts[file_idx] > 1:
                score -= DOUBLED_PAWN_PENALTY // 2

            # 2. Isolated pawn penalty (no friendly pawns on adjacent files)
            has_left_neighbor = (file_idx > 0 and file_counts[file_idx - 1] > 0)
            has_right_neighbor = (file_idx < 7 and file_counts[file_idx + 1] > 0)
            if not has_left_neighbor and not has_right_neighbor:
                score -= ISOLATED_PAWN_PENALTY

            # 3. Passed pawn bonus
            # Passed if no enemy pawns in front on same or adjacent files
            is_passed = True
            adjacent_files = [file_idx]
            if file_idx > 0:
                adjacent_files.append(file_idx - 1)
            if file_idx < 7:
                adjacent_files.append(file_idx + 1)

            for ef in adjacent_files:
                for er in range(8):
                    esq = chess.square(ef, er)
                    if esq in enemy_pawns:
                        if color == chess.WHITE and er > rank_idx:
                            is_passed = False
                            break
                        if color == chess.BLACK and er < rank_idx:
                            is_passed = False
                            break
                if not is_passed:
                    break

            if is_passed:
                advancement_rank = rank_idx if color == chess.WHITE else (7 - rank_idx)
                score += PASSED_PAWN_BONUS[advancement_rank]

        return score

    @classmethod
    def _evaluate_king_safety(cls, board: chess.Board, color: chess.Color, phase: float) -> int:
        """Evaluate king safety based on pawn shield and shelter (active in midgame)."""
        if phase < 0.15:
            # King safety less critical in endgames
            return 0

        score = 0
        king_sq = board.king(color)
        if king_sq is None:
            return 0

        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)

        # Check pawn shield in front of king
        friendly_pawns = board.pieces(chess.PAWN, color)
        shield_pawns = 0
        front_rank = king_rank + 1 if color == chess.WHITE else king_rank - 1

        if 0 <= front_rank <= 7:
            for f in range(max(0, king_file - 1), min(8, king_file + 2)):
                if chess.square(f, front_rank) in friendly_pawns:
                    shield_pawns += 1

        # Reward pawn shield
        score += shield_pawns * 15

        # Penalize open file near king
        enemy_rooks_queens = board.pieces(chess.ROOK, not color) | board.pieces(chess.QUEEN, not color)
        if enemy_rooks_queens:
            pawns_on_file = len([sq for sq in friendly_pawns if chess.square_file(sq) == king_file])
            if pawns_on_file == 0:
                score -= 25

        # Scale by game phase
        return int(score * phase)

    @classmethod
    def evaluate_detailed(cls, board: chess.Board) -> EvaluationBreakdown:
        """Perform comprehensive evaluation with sub-score attribution."""
        phase = cls._compute_phase(board)

        mat_w, mat_b = 0, 0
        pst_w, pst_b = 0, 0
        mob_w, mob_b = 0, 0

        # Bishop pair bonuses
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            mat_w += BISHOP_PAIR_BONUS
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            mat_b += BISHOP_PAIR_BONUS

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece:
                continue

            val = PIECE_VALUES[piece.piece_type]
            rank = chess.square_rank(square)
            file = chess.square_file(square)

            # Piece Square Table values
            if piece.piece_type == chess.KING:
                # Interpolate between midgame and endgame king tables
                mg_idx = (7 - rank) * 8 + file if piece.color == chess.WHITE else rank * 8 + file
                pos_val = int(
                    KING_TABLE_MIDGAME[mg_idx] * phase
                    + KING_TABLE_ENDGAME[mg_idx] * (1.0 - phase)
                )
            else:
                table = PST_MAP[piece.piece_type]
                pst_idx = (7 - rank) * 8 + file if piece.color == chess.WHITE else rank * 8 + file
                pos_val = table[pst_idx]

            # Mobility scoring: count attacked squares for non-pawns
            attacks_count = len(board.attacks(square)) if piece.piece_type != chess.PAWN else 0
            mobility_val = 0
            if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                mobility_val = attacks_count * 3
            elif piece.piece_type == chess.ROOK:
                mobility_val = attacks_count * 2
            elif piece.piece_type == chess.QUEEN:
                mobility_val = attacks_count * 1

            if piece.color == chess.WHITE:
                mat_w += val
                pst_w += pos_val
                mob_w += mobility_val
            else:
                mat_b += val
                pst_b += pos_val
                mob_b += mobility_val

        # King safety & pawn structure
        ks_w = cls._evaluate_king_safety(board, chess.WHITE, phase)
        ks_b = cls._evaluate_king_safety(board, chess.BLACK, phase)

        pawn_w = cls._evaluate_pawn_structure(board, chess.WHITE)
        pawn_b = cls._evaluate_pawn_structure(board, chess.BLACK)

        total_white = mat_w + pst_w + mob_w + ks_w + pawn_w
        total_black = mat_b + pst_b + mob_b + ks_b + pawn_b
        total = total_white - total_black

        return EvaluationBreakdown(
            total=total,
            material_white=mat_w,
            material_black=mat_b,
            pst_white=pst_w,
            pst_black=pst_b,
            mobility_white=mob_w,
            mobility_black=mob_b,
            king_safety_white=ks_w,
            king_safety_black=ks_b,
            pawn_structure_white=pawn_w,
            pawn_structure_black=pawn_b,
        )

    @classmethod
    def evaluate(cls, board: chess.Board) -> int:
        """Evaluate the board position from White's perspective (+ White advantage, - Black advantage)."""
        if board.is_checkmate():
            return -30000 if board.turn == chess.WHITE else 30000
        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        breakdown = cls.evaluate_detailed(board)
        return breakdown.total

    @classmethod
    def evaluate_relative(cls, board: chess.Board) -> int:
        """Evaluate the board from the active side's perspective (+ favors active player)."""
        white_score = cls.evaluate(board)
        return white_score if board.turn == chess.WHITE else -white_score

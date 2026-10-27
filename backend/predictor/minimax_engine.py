"""Minimax with Alpha-Beta Pruning Chess Engine Baseline.

Implements an independent classical chess search engine with:
- Material and positional Piece-Square Table (PST) evaluation
- Alpha-Beta pruning
- Move ordering (MVV-LVA captures and checks)
- Quiescence search for tactical stability
- Multi-candidate move ranking with principal variations
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import chess

from backend.chess_engine import ChessEngine, InvalidFENError
from backend.chess_engine.models import PieceColor
from backend.predictor.schemas import (
    AnalysisResult,
    EngineStatus,
    EvaluationScore,
    MoveCandidate,
    ScoreType,
)

# Piece Values in centipawns
PIECE_VALUES: Dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# Piece-Square Tables (oriented for White, mirrored for Black)
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

PST_MAP = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE_MIDGAME,
}

CHECKMATE_SCORE = 30000


class MinimaxEngine:
    """Minimax search engine with Alpha-Beta pruning and positional heuristics."""

    def __init__(self, default_depth: int = 3) -> None:
        """Initialize the Minimax search engine.

        Args:
            default_depth: Default search depth (typically 2-4 for fast response).
        """
        self.default_depth = default_depth
        self._nodes_evaluated = 0

    @classmethod
    def evaluate_board(cls, board: chess.Board) -> int:
        """Heuristically evaluate a static board position from White's perspective.

        Args:
            board: The board state to evaluate.

        Returns:
            Centipawn score relative to White (+ advantage for White, - for Black).
        """
        if board.is_checkmate():
            return -CHECKMATE_SCORE if board.turn == chess.WHITE else CHECKMATE_SCORE

        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        score = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if not piece:
                continue

            val = PIECE_VALUES[piece.piece_type]
            pst = PST_MAP[piece.piece_type]

            # Invert square index for White/Black PST lookup
            # chess.square 0 is a1 (bottom left).
            # PST index 0 is rank 8 (top left).
            rank = chess.square_rank(square)
            file = chess.square_file(square)

            if piece.color == chess.WHITE:
                pst_idx = (7 - rank) * 8 + file
                pos_val = pst[pst_idx]
                score += val + pos_val
            else:
                pst_idx = rank * 8 + file
                pos_val = pst[pst_idx]
                score -= val + pos_val

        return score

    def _order_moves(self, board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
        """Order moves to maximize Alpha-Beta pruning efficiency.

        Priority:
        1. Captures ordered by MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
        2. Promotions
        3. Checks
        4. Quiet moves
        """
        def move_score(move: chess.Move) -> int:
            score = 0
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                victim_val = PIECE_VALUES[victim.piece_type] if victim else 100
                attacker_val = PIECE_VALUES[attacker.piece_type] if attacker else 100
                # MVV-LVA formula
                score += 10000 + (victim_val * 10 - attacker_val)
            if move.promotion:
                score += 8000
            if board.gives_check(move):
                score += 5000
            return score

        return sorted(moves, key=move_score, reverse=True)

    def _quiescence(self, board: chess.Board, alpha: int, beta: int, max_depth: int = 2) -> int:
        """Quiescence search to mitigate the horizon effect on tactical capture sequences."""
        self._nodes_evaluated += 1
        stand_pat = self.evaluate_board(board)
        if board.turn == chess.BLACK:
            stand_pat = -stand_pat

        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        if max_depth <= 0:
            return alpha

        capture_moves = [m for m in board.legal_moves if board.is_capture(m)]
        ordered_captures = self._order_moves(board, capture_moves)

        for move in ordered_captures:
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha, max_depth - 1)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def _alpha_beta(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int = 1,
    ) -> Tuple[int, List[chess.Move]]:
        """Recursive Alpha-Beta minimax search with principal variation extraction.

        Returns:
            Tuple of (score_relative_to_active_player, principal_variation_moves).
        """
        self._nodes_evaluated += 1

        if board.is_checkmate():
            # Checkmate in current depth: unfavorable for active player
            return -CHECKMATE_SCORE + ply, []

        if board.is_stalemate() or board.is_insufficient_material():
            return 0, []

        if depth <= 0:
            q_score = self._quiescence(board, alpha, beta)
            return q_score, []

        best_score = -float("inf")
        best_pv: List[chess.Move] = []
        ordered_moves = self._order_moves(board, list(board.legal_moves))

        for move in ordered_moves:
            board.push(move)
            score, child_pv = self._alpha_beta(board, depth - 1, -beta, -alpha, ply + 1)
            score = -score
            board.pop()

            if score > best_score:
                best_score = score
                best_pv = [move] + child_pv

            if score > alpha:
                alpha = score

            if alpha >= beta:
                # Alpha-Beta cutoff
                break

        return int(best_score), best_pv

    def analyze(
        self,
        fen: str,
        depth: Optional[int] = None,
        candidate_count: int = 4,
    ) -> AnalysisResult:
        """Evaluate a position and return ranked candidate moves with variations.

        Args:
            fen: FEN string of the board position.
            depth: Search depth (default self.default_depth).
            candidate_count: Number of top candidate moves to return (default 4).

        Returns:
            AnalysisResult containing ranked candidate moves and evaluations.

        Raises:
            InvalidFENError: If the provided FEN is invalid or illegal.
        """
        start_time = time.perf_counter()
        search_depth = depth if depth is not None else self.default_depth
        self._nodes_evaluated = 0

        # Validate FEN using Module 1 ChessEngine
        try:
            engine = ChessEngine(fen)
        except Exception as err:
            raise InvalidFENError(fen, reason=str(err)) from err

        board = engine.board
        side_to_move = engine.turn

        # Handle terminal positions directly
        if board.is_checkmate():
            eval_score = EvaluationScore(
                score_type=ScoreType.MATE,
                value=0,
                mate_in_relative=0,
                mate_in_white=0,
                display_text="#",
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.TERMINAL_POSITION,
                engine_name="Minimax Alpha-Beta",
                nodes_evaluated=0,
                is_terminal=True,
                terminal_reason=f"Checkmate: {side_to_move.opposite.value.capitalize()} won",
            )

        if board.is_stalemate() or board.is_insufficient_material():
            eval_score = EvaluationScore(
                score_type=ScoreType.CENTIPAWN,
                value=0,
                score_relative_cp=0,
                score_white_cp=0,
                display_text="0.00",
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            reason = "Stalemate" if board.is_stalemate() else "Insufficient material"
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.TERMINAL_POSITION,
                engine_name="Minimax Alpha-Beta",
                nodes_evaluated=0,
                is_terminal=True,
                terminal_reason=reason,
            )

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.TERMINAL_POSITION,
                engine_name="Minimax Alpha-Beta",
                nodes_evaluated=0,
                is_terminal=True,
            )

        # Multi-candidate search: evaluate every root legal move
        root_candidates: List[Tuple[int, chess.Move, List[chess.Move]]] = []
        ordered_root_moves = self._order_moves(board, legal_moves)

        for root_move in ordered_root_moves:
            board.push(root_move)
            # Child searches at depth - 1, starting at ply 1
            score, child_pv = self._alpha_beta(
                board,
                depth=search_depth - 1,
                alpha=-CHECKMATE_SCORE * 2,
                beta=CHECKMATE_SCORE * 2,
                ply=1,
            )
            # Invert score to represent active player's advantage
            score = -score
            board.pop()
            pv = [root_move] + child_pv
            root_candidates.append((score, root_move, pv))

        # Sort candidate moves descending by score
        root_candidates.sort(key=lambda item: item[0], reverse=True)

        # Build candidate move objects
        candidates: List[MoveCandidate] = []
        best_move_uci: Optional[str] = None
        best_move_san: Optional[str] = None

        for rank_idx, (rel_score, move, pv) in enumerate(root_candidates[:candidate_count], start=1):
            is_best = (rank_idx == 1)

            # Score calculations
            is_mate = abs(rel_score) > (CHECKMATE_SCORE - 1000)
            if is_mate:
                score_type = ScoreType.MATE
                plies = CHECKMATE_SCORE - abs(rel_score)
                mate_dist = (plies + 1) // 2
                mate_in_rel = mate_dist if rel_score > 0 else -mate_dist
                mate_in_white = mate_in_rel if board.turn == chess.WHITE else -mate_in_rel
                val = mate_in_rel
                disp = f"+M{mate_in_rel}" if mate_in_rel > 0 else f"-M{abs(mate_in_rel)}"
                eval_obj = EvaluationScore(
                    score_type=score_type,
                    value=val,
                    mate_in_relative=mate_in_rel,
                    mate_in_white=mate_in_white,
                    display_text=disp,
                )
            else:
                score_type = ScoreType.CENTIPAWN
                val = rel_score
                white_cp = rel_score if board.turn == chess.WHITE else -rel_score
                disp_val = rel_score / 100.0
                disp = f"+{disp_val:.2f}" if disp_val > 0 else f"{disp_val:.2f}"
                eval_obj = EvaluationScore(
                    score_type=score_type,
                    value=val,
                    score_relative_cp=rel_score,
                    score_white_cp=white_cp,
                    display_text=disp,
                )

            # Convert PV to UCI and SAN
            pv_uci = [m.uci() for m in pv]
            pv_san: List[str] = []
            temp_board = board.copy()
            for pv_move in pv:
                if pv_move in temp_board.legal_moves:
                    pv_san.append(temp_board.san(pv_move))
                    temp_board.push(pv_move)
                else:
                    break

            san_move = board.san(move)
            if is_best:
                best_move_uci = move.uci()
                best_move_san = san_move

            candidate = MoveCandidate(
                rank=rank_idx,
                uci=move.uci(),
                san=san_move,
                evaluation=eval_obj,
                pv_uci=pv_uci,
                pv_san=pv_san,
                is_best_move=is_best,
            )
            candidates.append(candidate)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return AnalysisResult(
            fen=fen,
            side_to_move=side_to_move,
            best_move_uci=best_move_uci,
            best_move_san=best_move_san,
            candidates=candidates,
            search_depth=search_depth,
            analysis_time_ms=elapsed_ms,
            engine_status=EngineStatus.OK,
            engine_name="Minimax Alpha-Beta",
            nodes_evaluated=self._nodes_evaluated,
            is_terminal=False,
        )

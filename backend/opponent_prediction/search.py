"""Adversarial Search Engine for Module 3: Opponent Move Prediction.

Implements:
- Negamax search with Alpha-Beta pruning
- Iterative deepening with timeout-safe fallback
- Transposition table lookup and storage
- Move ordering integration (TT move, MVV-LVA, killers, history, checks)
- Quiescence search on captures
- Opponent response prediction across candidate moves
- Pure Minimax baseline for pruning efficiency comparisons
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple, Union

import chess

from backend.chess_engine import ChessEngine, IllegalMoveError, InvalidFENError
from backend.chess_engine.models import PieceColor
from backend.opponent_prediction.evaluation import PIECE_VALUES, PositionEvaluator
from backend.opponent_prediction.move_ordering import MoveOrderer
from backend.opponent_prediction.schemas import (
    CandidateConsequence,
    OpponentAnalysisReport,
    OpponentResponse,
    PredictionType,
    SearchStatus,
)
from backend.opponent_prediction.transposition_table import TTFlag, TranspositionTable
from backend.predictor.schemas import EvaluationScore, ScoreType

CHECKMATE_SCORE = 30000
INFINITY = 100000


class OpponentSearchEngine:
    """Adversarial search engine predicting opponent counter-moves."""

    def __init__(
        self,
        default_depth: int = 4,
        default_time_limit: float = 2.0,
        use_tt: bool = True,
        use_move_ordering: bool = True,
    ) -> None:
        """Initialize the OpponentSearchEngine.

        Args:
            default_depth: Default maximum search depth.
            default_time_limit: Default time limit in seconds per candidate move.
            use_tt: Enable transposition table caching.
            use_move_ordering: Enable move ordering heuristics.
        """
        self.default_depth = default_depth
        self.default_time_limit = default_time_limit
        self.use_tt = use_tt
        self.use_move_ordering = use_move_ordering

        self.tt = TranspositionTable() if use_tt else None
        self.move_orderer = MoveOrderer() if use_move_ordering else None

        self.nodes_evaluated = 0
        self._deadline: float = 0.0
        self._aborted: bool = False

    def _quiescence(self, board: chess.Board, alpha: int, beta: int, ply: int, max_depth: int = 4) -> int:
        """Quiescence search resolving dynamic capture sequences at leaf nodes."""
        self.nodes_evaluated += 1

        stand_pat = PositionEvaluator.evaluate_relative(board)

        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        if max_depth <= 0:
            return alpha

        capture_moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
        if not capture_moves:
            return stand_pat

        if self.use_move_ordering and self.move_orderer:
            ordered_captures = self.move_orderer.order_moves(board, capture_moves, ply=ply)
        else:
            ordered_captures = capture_moves

        for move in ordered_captures:
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha, ply + 1, max_depth - 1)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def negamax(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int = 0,
    ) -> Tuple[int, List[chess.Move]]:
        """Recursive Negamax search with Alpha-Beta pruning.

        Args:
            board: Current board state.
            depth: Search depth remaining.
            alpha: Alpha lower bound.
            beta: Beta upper bound.
            ply: Current search depth distance from root.

        Returns:
            Tuple of (score_relative_to_active_player, principal_variation_moves).
        """
        self.nodes_evaluated += 1

        # Periodic time check (every 1024 nodes)
        if self._deadline > 0 and (self.nodes_evaluated & 1023) == 0:
            if time.perf_counter() >= self._deadline:
                self._aborted = True
                return 0, []

        # 1. Terminal positions handled first
        if board.is_checkmate():
            return -CHECKMATE_SCORE + ply, []
        if (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.can_claim_threefold_repetition()
            or board.can_claim_fifty_moves()
        ):
            return 0, []

        # 2. Transposition table lookup
        tt_key = self.tt.get_zobrist_key(board) if self.use_tt and self.tt else 0
        tt_move = None
        if self.use_tt and self.tt:
            tt_val, tt_move = self.tt.lookup(tt_key, depth, alpha, beta, ply)
            if tt_val is not None:
                return tt_val, [tt_move] if tt_move else []

        # 3. Base case (depth == 0) -> Quiescence search
        if depth <= 0:
            q_score = self._quiescence(board, alpha, beta, ply)
            return q_score, []

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return 0, []

        # 4. Move ordering
        if self.use_move_ordering and self.move_orderer:
            ordered_moves = self.move_orderer.order_moves(
                board, legal_moves, tt_move=tt_move, ply=ply
            )
        else:
            ordered_moves = legal_moves

        best_score = -INFINITY
        best_pv: List[chess.Move] = []
        best_move: Optional[chess.Move] = None
        orig_alpha = alpha

        for move in ordered_moves:
            board.push(move)
            score, child_pv = self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            score = -score
            board.pop()

            if self._aborted:
                return 0, []

            if score > best_score:
                best_score = score
                best_move = move
                best_pv = [move] + child_pv

            if score > alpha:
                alpha = score

            if alpha >= beta:
                # Beta cutoff
                if self.use_move_ordering and self.move_orderer:
                    self.move_orderer.record_cutoff(board, move, depth, ply)
                if self.use_tt and self.tt:
                    self.tt.store(tt_key, depth, best_score, TTFlag.LOWERBOUND, best_move, ply)
                break

        # Transposition table storage
        if self.use_tt and self.tt and not self._aborted:
            flag = TTFlag.EXACT if alpha > orig_alpha else TTFlag.UPPERBOUND
            self.tt.store(tt_key, depth, best_score, flag, best_move, ply)

        return best_score, best_pv

    def search_without_pruning(
        self,
        board: chess.Board,
        depth: int,
    ) -> Tuple[int, int]:
        """Pure Minimax search without Alpha-Beta pruning to measure pruning efficiency.

        Returns:
            Tuple of (score, nodes_evaluated).
        """
        nodes = [0]

        def pure_minimax(b: chess.Board, d: int, ply: int) -> int:
            nodes[0] += 1
            if b.is_checkmate():
                return -CHECKMATE_SCORE + ply
            if (
                b.is_stalemate()
                or b.is_insufficient_material()
                or b.can_claim_threefold_repetition()
                or b.can_claim_fifty_moves()
            ):
                return 0
            if d <= 0:
                return self._quiescence(b, -INFINITY, INFINITY, ply)

            legal = list(b.legal_moves)
            if not legal:
                return 0

            max_val = -INFINITY
            for move in legal:
                b.push(move)
                val = -pure_minimax(b, d - 1, ply + 1)
                b.pop()
                if val > max_val:
                    max_val = val
            return max_val

        score = pure_minimax(board, depth, 0)
        return score, nodes[0]

    def iterative_deepening(
        self,
        board: chess.Board,
        max_depth: int,
        time_limit: Optional[float] = None,
    ) -> Tuple[int, List[chess.Move], int, SearchStatus]:
        """Execute iterative deepening search with timeout protection.

        Returns:
            Tuple of (best_score, principal_variation, completed_depth, search_status).
        """
        self.nodes_evaluated = 0
        self._aborted = False
        start_time = time.perf_counter()
        self._deadline = (start_time + time_limit) if time_limit else 0.0

        best_score = 0
        best_pv: List[chess.Move] = []
        completed_depth = 0
        status = SearchStatus.COMPLETED

        if self.tt:
            self.tt.increment_age()

        for cur_depth in range(1, max_depth + 1):
            if self._deadline > 0 and time.perf_counter() >= self._deadline:
                status = SearchStatus.TIMEOUT_INTERRUPTED
                break

            score, pv = self.negamax(
                board,
                depth=cur_depth,
                alpha=-INFINITY,
                beta=INFINITY,
                ply=0,
            )

            if self._aborted:
                status = SearchStatus.TIMEOUT_INTERRUPTED
                break

            best_score = score
            best_pv = pv
            completed_depth = cur_depth

            # If checkmate found at shallow depth, stop early
            if abs(best_score) > (CHECKMATE_SCORE - 100):
                break

        return best_score, best_pv, completed_depth, status

    def analyze_candidate_consequences(
        self,
        fen_or_engine: Union[str, ChessEngine],
        candidate_moves: Optional[List[Union[str, chess.Move]]] = None,
        depth: Optional[int] = None,
        time_limit_per_move: Optional[float] = None,
    ) -> OpponentAnalysisReport:
        """Evaluate candidate moves and predict the strongest opponent responses.

        Args:
            fen_or_engine: FEN string or ChessEngine instance.
            candidate_moves: List of candidate moves to examine. If None, all legal moves.
            depth: Maximum search depth per candidate.
            time_limit_per_move: Time budget in seconds per candidate move.

        Returns:
            OpponentAnalysisReport containing consequences of each candidate move.
        """
        start_all = time.perf_counter()
        search_depth = depth if depth is not None else self.default_depth
        move_time_limit = (
            time_limit_per_move if time_limit_per_move is not None else self.default_time_limit
        )

        if isinstance(fen_or_engine, ChessEngine):
            engine = fen_or_engine
        else:
            try:
                engine = ChessEngine(fen_or_engine)
            except Exception as err:
                raise InvalidFENError(str(fen_or_engine), reason=str(err)) from err

        board = engine.board
        active_color = engine.turn
        opponent_color = active_color.opposite

        # Determine moves to analyze
        if candidate_moves is None or len(candidate_moves) == 0:
            moves_to_check = list(board.legal_moves)
        else:
            moves_to_check = []
            for m in candidate_moves:
                parsed_move = engine.parse_move(m)
                if parsed_move not in board.legal_moves:
                    raise IllegalMoveError(
                        move_str=str(m),
                        fen=engine.fen,
                        reason="Candidate move is illegal in starting position",
                    )
                moves_to_check.append(parsed_move)

        consequences: List[CandidateConsequence] = []
        total_nodes = 0

        for cand_move in moves_to_check:
            cand_uci = cand_move.uci()
            cand_san = board.san(cand_move)
            t_cand_start = time.perf_counter()

            # Material before move
            mat_before = PositionEvaluator.evaluate(board)

            # 1. Simulate playing the candidate move
            board.push(cand_move)

            # Check if candidate move delivered checkmate or terminal state directly
            if board.is_checkmate():
                # Opponent is checkmated! No response possible.
                board.pop()
                dur_ms = (time.perf_counter() - t_cand_start) * 1000
                eval_obj = EvaluationScore(
                    score_type=ScoreType.MATE,
                    value=1,
                    mate_in_relative=1,
                    mate_in_white=1 if active_color == PieceColor.WHITE else -1,
                    display_text="+M1",
                )
                consequence = CandidateConsequence(
                    candidate_move_uci=cand_uci,
                    candidate_move_san=cand_san,
                    predicted_opponent_response=None,
                    post_candidate_evaluation=eval_obj,
                    pv_uci=[],
                    pv_san=[],
                    search_depth=1,
                    nodes_evaluated=1,
                    search_duration_ms=dur_ms,
                    is_forced_mate=True,
                    mate_in=1,
                    status=SearchStatus.TERMINAL,
                    material_delta=CHECKMATE_SCORE,
                )
                consequences.append(consequence)
                continue

            if board.is_stalemate() or board.is_insufficient_material():
                board.pop()
                dur_ms = (time.perf_counter() - t_cand_start) * 1000
                eval_obj = EvaluationScore(
                    score_type=ScoreType.CENTIPAWN,
                    value=0,
                    score_relative_cp=0,
                    score_white_cp=0,
                    display_text="0.00",
                )
                consequence = CandidateConsequence(
                    candidate_move_uci=cand_uci,
                    candidate_move_san=cand_san,
                    predicted_opponent_response=None,
                    post_candidate_evaluation=eval_obj,
                    pv_uci=[],
                    pv_san=[],
                    search_depth=1,
                    nodes_evaluated=1,
                    search_duration_ms=dur_ms,
                    is_forced_mate=False,
                    mate_in=None,
                    status=SearchStatus.TERMINAL,
                    material_delta=0,
                )
                consequences.append(consequence)
                continue

            # 2. Run adversarial search to find the opponent's best response
            opp_score, opp_pv, comp_depth, search_status = self.iterative_deepening(
                board,
                max_depth=search_depth,
                time_limit=move_time_limit,
            )
            total_nodes += self.nodes_evaluated
            dur_ms = (time.perf_counter() - t_cand_start) * 1000

            # Revert candidate move
            board.pop()

            # Opponent's score is from opponent's perspective.
            # Invert to express from current player's perspective:
            player_eval_score = -opp_score

            # Identify forced mate conditions
            is_mate = abs(opp_score) > (CHECKMATE_SCORE - 1000)
            if is_mate:
                score_type = ScoreType.MATE
                plies = CHECKMATE_SCORE - abs(opp_score)
                mate_dist = (plies + 1) // 2
                # If player_eval_score > 0, player forces mate; else opponent forces mate
                mate_in_rel = mate_dist if player_eval_score > 0 else -mate_dist
                mate_in_white = mate_in_rel if active_color == PieceColor.WHITE else -mate_in_rel
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
                val = player_eval_score
                white_cp = player_eval_score if active_color == PieceColor.WHITE else -player_eval_score
                disp_val = player_eval_score / 100.0
                disp = f"+{disp_val:.2f}" if disp_val > 0 else f"{disp_val:.2f}"
                eval_obj = EvaluationScore(
                    score_type=score_type,
                    value=val,
                    score_relative_cp=player_eval_score,
                    score_white_cp=white_cp,
                    display_text=disp,
                )

            # Extract opponent response
            opp_response: Optional[OpponentResponse] = None
            pv_uci: List[str] = [m.uci() for m in opp_pv]
            pv_san: List[str] = []

            if opp_pv:
                opp_move = opp_pv[0]
                board.push(cand_move)
                opp_san = board.san(opp_move)
                is_chk = board.gives_check(opp_move)
                is_cap = board.is_capture(opp_move)

                # Reconstruct full PV in SAN
                temp_b = board.copy()
                for m in opp_pv:
                    if m in temp_b.legal_moves:
                        pv_san.append(temp_b.san(m))
                        temp_b.push(m)
                    else:
                        break
                board.pop()

                # Determine tactical threat
                threat = None
                if is_mate and player_eval_score < 0:
                    threat = f"Forced checkmate in {abs(mate_dist)} move(s)"
                elif is_chk:
                    threat = "Check against king"
                elif is_cap:
                    threat = "Material capture"

                # Opponent's own evaluation of their response
                opp_eval = EvaluationScore(
                    score_type=eval_obj.score_type,
                    value=opp_score,
                    score_relative_cp=opp_score,
                    score_white_cp=-eval_obj.score_white_cp if eval_obj.score_white_cp is not None else None,
                    mate_in_relative=-eval_obj.mate_in_relative if eval_obj.mate_in_relative is not None else None,
                    display_text=f"{opp_score/100.0:+.2f}" if not is_mate else f"{'-M' if opp_score < 0 else '+M'}{abs(mate_dist)}",
                )

                opp_response = OpponentResponse(
                    move_uci=opp_move.uci(),
                    move_san=opp_san,
                    evaluation=opp_eval,
                    pv_uci=pv_uci,
                    pv_san=pv_san,
                    is_forced_mate=is_mate,
                    mate_in=mate_dist if is_mate else None,
                    is_check=is_chk,
                    is_capture=is_cap,
                    tactical_threat=threat,
                )

            mat_delta = PositionEvaluator.evaluate(board) - mat_before
            if active_color == PieceColor.BLACK:
                mat_delta = -mat_delta

            consequence = CandidateConsequence(
                candidate_move_uci=cand_uci,
                candidate_move_san=cand_san,
                predicted_opponent_response=opp_response,
                post_candidate_evaluation=eval_obj,
                pv_uci=pv_uci,
                pv_san=pv_san,
                search_depth=comp_depth,
                nodes_evaluated=self.nodes_evaluated,
                search_duration_ms=dur_ms,
                is_forced_mate=is_mate,
                mate_in=mate_dist if is_mate else None,
                status=search_status,
                material_delta=mat_delta,
                prediction_type=PredictionType.ADVERSARIAL_MINIMAX,
            )
            consequences.append(consequence)

        # Sort candidate consequences: highest player evaluation first
        consequences.sort(
            key=lambda c: (
                1 if c.post_candidate_evaluation.score_type == ScoreType.MATE and c.post_candidate_evaluation.value > 0 else 0,
                c.post_candidate_evaluation.value,
            ),
            reverse=True,
        )

        best_cand_uci = consequences[0].candidate_move_uci if consequences else None
        best_cand_san = consequences[0].candidate_move_san if consequences else None
        total_time_ms = (time.perf_counter() - start_all) * 1000

        return OpponentAnalysisReport(
            fen=engine.fen,
            side_to_move=active_color,
            opponent_side=opponent_color,
            consequences=consequences,
            best_candidate_uci=best_cand_uci,
            best_candidate_san=best_cand_san,
            total_nodes=total_nodes,
            total_duration_ms=total_time_ms,
        )

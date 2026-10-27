"""Move Ordering heuristics for Alpha-Beta Pruning.

Implements:
- TT / Hash best move priority
- MVV-LVA (Most Valuable Victim - Least Valuable Attacker) capture ordering
- Pawn promotion priority
- Killer move heuristic (two killer moves per search ply)
- History heuristic (frequency of cutoffs by quiet moves scaled by depth^2)
- Check priority
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import chess
from backend.opponent_prediction.evaluation import PIECE_VALUES


class MoveOrderer:
    """Ranks legal moves to maximize alpha-beta pruning cutoffs."""

    def __init__(self) -> None:
        """Initialize killer move tables and history heuristics."""
        # killer_moves[ply] = [primary_killer, secondary_killer]
        self._killer_moves: Dict[int, List[chess.Move]] = {}
        # history[(color, from_sq, to_sq)] = score
        self._history_table: Dict[Tuple[chess.Color, chess.Square, chess.Square], int] = {}

    def clear(self) -> None:
        """Reset killer moves and history heuristic data."""
        self._killer_moves.clear()
        self._history_table.clear()

    def record_cutoff(
        self,
        board: chess.Board,
        move: chess.Move,
        depth: int,
        ply: int,
    ) -> None:
        """Record a beta cutoff move to inform killer and history heuristics.

        Args:
            board: Current board state.
            move: Move causing beta cutoff.
            depth: Search depth remaining.
            ply: Current search ply.
        """
        # If quiet move (not a capture or promotion), record killer and history
        if not board.is_capture(move) and not move.promotion:
            # 1. Update killer moves (store up to 2 distinct killers per ply)
            killers = self._killer_moves.setdefault(ply, [])
            if move not in killers:
                killers.insert(0, move)
                if len(killers) > 2:
                    killers.pop()

            # 2. Update history heuristic
            hist_key = (board.turn, move.from_square, move.to_square)
            self._history_table[hist_key] = (
                self._history_table.get(hist_key, 0) + depth * depth
            )

    def order_moves(
        self,
        board: chess.Board,
        moves: List[chess.Move],
        tt_move: Optional[chess.Move] = None,
        ply: int = 0,
    ) -> List[chess.Move]:
        """Assign priority scores to moves and sort descending.

        Args:
            board: Current board state.
            moves: List of legal moves.
            tt_move: Best move suggested from transposition table / PV.
            ply: Current search ply distance.

        Returns:
            Sorted list of legal moves.
        """
        killers = self._killer_moves.get(ply, [])
        primary_killer = killers[0] if len(killers) > 0 else None
        secondary_killer = killers[1] if len(killers) > 1 else None

        def score_move(move: chess.Move) -> int:
            # 1. TT / PV move
            if tt_move and move == tt_move:
                return 1_000_000

            # 2. Captures via MVV-LVA
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                victim_val = PIECE_VALUES[victim.piece_type] if victim else 100
                attacker_val = PIECE_VALUES[attacker.piece_type] if attacker else 100
                return 50_000 + (victim_val * 10 - attacker_val)

            # 3. Pawn promotions
            if move.promotion:
                if move.promotion == chess.QUEEN:
                    return 45_000
                return 30_000

            # 4. Killer moves
            if primary_killer and move == primary_killer:
                return 20_000
            if secondary_killer and move == secondary_killer:
                return 15_000

            # 5. Checks
            if board.gives_check(move):
                return 10_000

            # 6. History heuristic
            hist_key = (board.turn, move.from_square, move.to_square)
            hist_score = self._history_table.get(hist_key, 0)
            return min(hist_score, 8_000)

        return sorted(moves, key=score_move, reverse=True)

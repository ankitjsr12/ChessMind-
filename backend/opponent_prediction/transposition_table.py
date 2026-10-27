"""Transposition Table with Zobrist Hashing for Adversarial Search.

Caches evaluations, search depths, bounds (exact, lower bound, upper bound),
and best moves to avoid re-evaluating transposed game positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Tuple

import chess
import chess.polyglot


class TTFlag(IntEnum):
    """Transposition table node evaluation bounds."""

    EXACT = 0       # Exact minimax score
    LOWERBOUND = 1  # Beta cutoff (score >= beta, fail-high)
    UPPERBOUND = 2  # Alpha fail-low (score <= alpha)


MATE_SCORE_THRESHOLD = 28000


@dataclass
class TTEntry:
    """Entry stored within the transposition table."""

    key: int
    depth: int
    value: int
    flag: TTFlag
    best_move: Optional[chess.Move]
    age: int = 0


class TranspositionTable:
    """Hash table caching search results keyed by 64-bit Zobrist position hashes."""

    def __init__(self, max_entries: int = 200_000) -> None:
        """Initialize the Transposition Table.

        Args:
            max_entries: Maximum number of entries stored before replacing.
        """
        self.max_entries = max_entries
        self._table: Dict[int, TTEntry] = {}
        self._age = 0
        self.hits = 0
        self.misses = 0

    def increment_age(self) -> None:
        """Advance search generation age for aging out obsolete positions."""
        self._age += 1

    def clear(self) -> None:
        """Clear all entries in the table and reset metrics."""
        self._table.clear()
        self.hits = 0
        self.misses = 0

    @classmethod
    def get_zobrist_key(cls, board: chess.Board) -> int:
        """Compute the 64-bit Zobrist hash key for the given board state."""
        return chess.polyglot.zobrist_hash(board)

    def store(
        self,
        key: int,
        depth: int,
        value: int,
        flag: TTFlag,
        best_move: Optional[chess.Move],
        ply: int = 0,
    ) -> None:
        """Store an evaluated position into the transposition table.

        Args:
            key: 64-bit Zobrist key.
            depth: Remaining search depth when position was evaluated.
            value: Score from search.
            flag: Exact, lowerbound, or upperbound indicator.
            best_move: Best move found from this position.
            ply: Search ply distance from root (for mate score adjustment).
        """
        # Normalize mate scores to be ply-independent
        stored_value = value
        if value > MATE_SCORE_THRESHOLD:
            stored_value = value + ply
        elif value < -MATE_SCORE_THRESHOLD:
            stored_value = value - ply

        # Replacement strategy: replace if new search is deeper or entry is from older generation
        existing = self._table.get(key)
        if (
            existing is None
            or depth >= existing.depth
            or existing.age != self._age
            or flag == TTFlag.EXACT
        ):
            if len(self._table) >= self.max_entries and key not in self._table:
                # Evict an entry if table is full
                # In python dict, popping arbitrary or oldest item
                self._table.pop(next(iter(self._table)))

            self._table[key] = TTEntry(
                key=key,
                depth=depth,
                value=stored_value,
                flag=flag,
                best_move=best_move,
                age=self._age,
            )

    def lookup(
        self,
        key: int,
        depth: int,
        alpha: int,
        beta: int,
        ply: int = 0,
    ) -> Tuple[Optional[int], Optional[chess.Move]]:
        """Look up position in the transposition table.

        Args:
            key: 64-bit Zobrist key.
            depth: Current search depth required.
            alpha: Current alpha bound.
            beta: Current beta bound.
            ply: Current search ply distance.

        Returns:
            Tuple of (score_if_usable, best_move_hint).
            If score cannot produce a cutoff, score is None but best_move_hint may still be returned!
        """
        entry = self._table.get(key)
        if entry is None:
            self.misses += 1
            return None, None

        self.hits += 1

        # Denormalize mate score relative to current ply
        ret_val = entry.value
        if entry.value > MATE_SCORE_THRESHOLD:
            ret_val = entry.value - ply
        elif entry.value < -MATE_SCORE_THRESHOLD:
            ret_val = entry.value + ply

        # Check if stored depth is sufficient for a cutoff
        if entry.depth >= depth:
            if entry.flag == TTFlag.EXACT:
                return ret_val, entry.best_move
            if entry.flag == TTFlag.LOWERBOUND and ret_val >= beta:
                return ret_val, entry.best_move
            if entry.flag == TTFlag.UPPERBOUND and ret_val <= alpha:
                return ret_val, entry.best_move

        # Return best_move hint for move ordering even if score cannot cause cutoff
        return None, entry.best_move

    def __len__(self) -> int:
        return len(self._table)

    @property
    def hit_rate(self) -> float:
        """Return the transposition table hit rate ratio."""
        total = self.hits + self.misses
        return (self.hits / total) if total > 0 else 0.0

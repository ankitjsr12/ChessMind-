"""Move Ranker and Comparison Interface for ChessMind AI.

Coordinates Stockfish multipv analysis, integrates the Minimax + Alpha-Beta
baseline, produces ranked candidate moves, provides side-by-side engine
comparisons, and implements the BaseMovePredictor protocol for ChessEngine play.
"""

from __future__ import annotations

from typing import List, Optional

from backend.chess_engine import ChessEngine, InvalidFENError
from backend.chess_engine.models import BaseMovePredictor, PieceColor
from backend.predictor.minimax_engine import MinimaxEngine
from backend.predictor.schemas import (
    AnalysisResult,
    ComparisonResult,
    EngineStatus,
    MoveCandidate,
)
from backend.predictor.stockfish_service import (
    StockfishNotFoundError,
    StockfishService,
)


class MoveRanker:
    """Orchestrates chess move analysis using Stockfish and Minimax search engines."""

    def __init__(
        self,
        stockfish_service: Optional[StockfishService] = None,
        minimax_engine: Optional[MinimaxEngine] = None,
    ) -> None:
        """Initialize MoveRanker.

        Args:
            stockfish_service: Optional custom StockfishService instance.
            minimax_engine: Optional custom MinimaxEngine instance.
        """
        self.stockfish = stockfish_service or StockfishService()
        self.minimax = minimax_engine or MinimaxEngine()

    def close(self) -> None:
        """Safely close engine subprocesses."""
        self.stockfish.close()

    def __enter__(self) -> MoveRanker:
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def predict_best_moves(
        self,
        fen: str,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
        candidate_count: int = 4,
        fallback_to_minimax: bool = True,
    ) -> AnalysisResult:
        """Analyze position and recommend the best move along with top alternative candidates.

        Args:
            fen: FEN string of the chess position.
            depth: Search depth.
            time_limit: Time limit in seconds.
            candidate_count: Total number of candidates (best + alternatives).
            fallback_to_minimax: If True, uses Minimax when Stockfish is unavailable.

        Returns:
            AnalysisResult with ranked candidates, evaluations, and PVs.

        Raises:
            InvalidFENError: If FEN is invalid or illegal.
            StockfishNotFoundError: If Stockfish is missing and fallback_to_minimax is False.
        """
        # Validate FEN using Module 1 ChessEngine
        try:
            ChessEngine(fen)
        except Exception as err:
            raise InvalidFENError(fen, reason=str(err)) from err

        # If Stockfish is available, perform Stockfish multipv analysis
        if self.stockfish.is_available():
            try:
                return self.stockfish.analyze(
                    fen=fen,
                    depth=depth,
                    time_limit=time_limit,
                    multipv=candidate_count,
                    strict=True,
                )
            except Exception:
                if not fallback_to_minimax:
                    raise

        # If Stockfish unavailable or failed and fallback is enabled
        if fallback_to_minimax:
            minimax_depth = depth if depth is not None and depth <= 5 else 3
            result = self.minimax.analyze(
                fen=fen,
                depth=minimax_depth,
                candidate_count=candidate_count,
            )
            result.engine_name = f"{result.engine_name} (Fallback)"
            return result

        raise StockfishNotFoundError(searched_paths=self.stockfish.DEFAULT_SEARCH_PATHS)

    def compare_stockfish_and_minimax(
        self,
        fen: str,
        stockfish_depth: int = 12,
        minimax_depth: int = 3,
        time_limit: float = 2.0,
        candidate_count: int = 3,
    ) -> ComparisonResult:
        """Evaluate position with both Stockfish and Minimax to compare evaluations.

        Args:
            fen: Position in FEN notation.
            stockfish_depth: Search depth for Stockfish.
            minimax_depth: Search depth for Minimax.
            time_limit: Time limit for Stockfish.
            candidate_count: Number of candidates to evaluate per engine.

        Returns:
            ComparisonResult containing both evaluations and an agreement summary.
        """
        # Minimax baseline evaluation
        minimax_res = self.minimax.analyze(
            fen=fen,
            depth=minimax_depth,
            candidate_count=candidate_count,
        )

        # Stockfish evaluation (if available)
        stockfish_res: Optional[AnalysisResult] = None
        if self.stockfish.is_available():
            try:
                stockfish_res = self.stockfish.analyze(
                    fen=fen,
                    depth=stockfish_depth,
                    time_limit=time_limit,
                    multipv=candidate_count,
                    strict=False,
                )
            except Exception:
                stockfish_res = None

        # Determine agreement
        if stockfish_res and stockfish_res.best_move_uci and minimax_res.best_move_uci:
            agreement = (stockfish_res.best_move_uci == minimax_res.best_move_uci)
            sf_move = stockfish_res.best_move_san
            mm_move = minimax_res.best_move_san
            if agreement:
                summary = f"Consensus: Both engines recommend {sf_move}."
            else:
                summary = (
                    f"Divergence: Stockfish recommends {sf_move} while Minimax recommends {mm_move}."
                )
        elif not stockfish_res:
            agreement = False
            summary = (
                f"Minimax evaluated best move as {minimax_res.best_move_san}. "
                "Stockfish was unavailable for comparison."
            )
        else:
            agreement = True
            summary = "Position is terminal or has no legal moves."

        return ComparisonResult(
            fen=fen,
            side_to_move=minimax_res.side_to_move,
            stockfish_analysis=stockfish_res,
            minimax_analysis=minimax_res,
            agreement=agreement,
            summary=summary,
        )

    # -------------------------------------------------------------------------
    # BaseMovePredictor Protocol Implementation
    # -------------------------------------------------------------------------

    def predict_move(self, fen: str, legal_moves_uci: List[str]) -> Optional[str]:
        """Predict the next best move adhering to Module 1's BaseMovePredictor protocol.

        Args:
            fen: Board position in FEN notation.
            legal_moves_uci: List of legal moves in UCI format.

        Returns:
            Legal UCI move string or None.
        """
        if not legal_moves_uci:
            return None

        result = self.predict_best_moves(fen, candidate_count=1, fallback_to_minimax=True)
        if result.best_move_uci and result.best_move_uci in legal_moves_uci:
            return result.best_move_uci

        # Fallback to first candidate if available
        if result.candidates and result.candidates[0].uci in legal_moves_uci:
            return result.candidates[0].uci

        return legal_moves_uci[0]

"""Stockfish UCI Engine Integration Service for ChessMind AI.

Manages the Stockfish subprocess lifecycle via the UCI protocol, handles multipv
analysis to extract top candidate moves with principal variations, normalizes
evaluations from both relative and absolute perspectives, and provides safe
process cleanup and comprehensive error handling.
"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any, Dict, List, Optional

import chess
import chess.engine

from backend.chess_engine import ChessEngine, InvalidFENError
from backend.chess_engine.models import PieceColor
from backend.predictor.schemas import (
    AnalysisResult,
    EngineStatus,
    EvaluationScore,
    MoveCandidate,
    ScoreType,
)


class StockfishException(Exception):
    """Base exception for Stockfish integration errors."""


class StockfishNotFoundError(StockfishException):
    """Raised when the Stockfish executable binary cannot be located."""

    def __init__(
        self,
        searched_paths: List[str],
        message: str = "Stockfish executable not found",
    ) -> None:
        super().__init__(
            f"{message}. Searched paths: {searched_paths}. "
            "Please install Stockfish ('brew install stockfish' or 'apt install stockfish') "
            "or set the STOCKFISH_PATH environment variable."
        )
        self.searched_paths = searched_paths


class StockfishEngineError(StockfishException):
    """Raised when the Stockfish process encounters a UCI protocol or runtime error."""


class AnalysisTimeoutError(StockfishException):
    """Raised when analysis exceeds the specified timeout threshold."""


class StockfishService:
    """Service for interacting with the Stockfish UCI engine."""

    # Standard locations for the Stockfish binary
    DEFAULT_SEARCH_PATHS = [
        "/opt/homebrew/bin/stockfish",
        "/opt/homebrew/opt/stockfish/bin/stockfish",
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
        "/usr/games/stockfish",
        "C:\\Program Files\\Stockfish\\stockfish.exe",
        "C:\\stockfish\\stockfish.exe",
    ]

    def __init__(
        self,
        executable_path: Optional[str] = None,
        default_depth: int = 15,
        default_time_limit: float = 2.0,
        multipv: int = 4,
        engine_instance: Optional[chess.engine.SimpleEngine] = None,
    ) -> None:
        """Initialize StockfishService.

        Args:
            executable_path: Explicit path to Stockfish binary. If None, auto-detected.
            default_depth: Default search depth for analysis.
            default_time_limit: Default maximum time in seconds for analysis.
            multipv: Number of principal variations to compute (default 4).
            engine_instance: Optional injected SimpleEngine instance (useful for testing/mocking).
        """
        self.executable_path = executable_path or self.find_stockfish_binary()
        self.default_depth = default_depth
        self.default_time_limit = default_time_limit
        self.multipv = multipv
        self._engine: Optional[chess.engine.SimpleEngine] = engine_instance

    @classmethod
    def find_stockfish_binary(cls) -> Optional[str]:
        """Locate the Stockfish binary on the system.

        Checks:
        1. STOCKFISH_PATH environment variable
        2. System PATH via shutil.which
        3. Common macOS, Linux, and Windows directories
        """
        env_path = os.environ.get("STOCKFISH_PATH")
        if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            return env_path

        which_path = shutil.which("stockfish")
        if which_path:
            return which_path

        for path in cls.DEFAULT_SEARCH_PATHS:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return None

    def is_available(self) -> bool:
        """Check if Stockfish is installed and accessible."""
        if self._engine is not None:
            return True
        return self.executable_path is not None and os.path.isfile(self.executable_path)

    def _get_or_create_engine(self) -> chess.engine.SimpleEngine:
        """Get or lazily start the Stockfish UCI process."""
        if self._engine is not None:
            return self._engine

        if not self.executable_path or not os.path.isfile(self.executable_path):
            searched = [self.executable_path] if self.executable_path else []
            searched.extend(self.DEFAULT_SEARCH_PATHS)
            raise StockfishNotFoundError(searched_paths=[p for p in searched if p])

        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.executable_path)
            return self._engine
        except Exception as err:
            raise StockfishEngineError(f"Failed to start Stockfish process: {err}") from err

    def close(self) -> None:
        """Safely terminate the Stockfish engine process and release resources."""
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            finally:
                self._engine = None

    def __enter__(self) -> StockfishService:
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit releasing engine process."""
        self.close()

    def analyze(
        self,
        fen: str,
        depth: Optional[int] = None,
        time_limit: Optional[float] = None,
        multipv: Optional[int] = None,
        strict: bool = True,
    ) -> AnalysisResult:
        """Analyze a chess position using Stockfish multipv analysis.

        Args:
            fen: The chess position in FEN notation.
            depth: Search depth limit (default self.default_depth).
            time_limit: Time limit in seconds (default self.default_time_limit).
            multipv: Number of candidate variations (default self.multipv).
            strict: If True, raises exceptions when Stockfish is unavailable or fails.
                   If False, returns structured AnalysisResult with error status.

        Returns:
            AnalysisResult containing ranked candidate moves, evaluations, and PVs.

        Raises:
            InvalidFENError: If the FEN string is invalid or illegal.
            StockfishNotFoundError: If strict=True and Stockfish binary is missing.
            StockfishEngineError: If strict=True and the UCI process fails.
        """
        start_time = time.perf_counter()

        # 1. Validate position using Module 1 ChessEngine
        try:
            engine_validator = ChessEngine(fen)
        except Exception as err:
            raise InvalidFENError(fen, reason=str(err)) from err

        board = engine_validator.board
        side_to_move = engine_validator.turn

        # 2. Check for terminal positions (Checkmate, Stalemate, Draw)
        if board.is_checkmate():
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            winner = side_to_move.opposite
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.TERMINAL_POSITION,
                engine_name="Stockfish (Terminal)",
                nodes_evaluated=0,
                is_terminal=True,
                terminal_reason=f"Checkmate: {winner.value.capitalize()} won",
            )

        if board.is_stalemate() or board.is_insufficient_material():
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
                engine_name="Stockfish (Terminal)",
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
                engine_name="Stockfish (Terminal)",
                nodes_evaluated=0,
                is_terminal=True,
            )

        # 3. Check engine availability
        if not self.is_available():
            if strict:
                searched = [self.executable_path] if self.executable_path else []
                searched.extend(self.DEFAULT_SEARCH_PATHS)
                raise StockfishNotFoundError(searched_paths=[p for p in searched if p])
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.NOT_AVAILABLE,
                engine_name="Stockfish (Unavailable)",
            )

        # 4. Configure search limits and multipv
        search_depth = depth if depth is not None else self.default_depth
        search_time = time_limit if time_limit is not None else self.default_time_limit
        effective_multipv = min(
            multipv if multipv is not None else self.multipv, len(legal_moves)
        )
        limit = chess.engine.Limit(depth=search_depth, time=search_time)

        try:
            engine = self._get_or_create_engine()
            # Perform multipv analysis
            infos = engine.analyse(board, limit=limit, multipv=effective_multipv)
            if not isinstance(infos, list):
                infos = [infos]
        except chess.engine.EngineTerminatedError as err:
            self._engine = None
            if strict:
                raise StockfishEngineError(f"Stockfish terminated unexpectedly: {err}") from err
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.ERROR,
                engine_name="Stockfish",
            )
        except Exception as err:
            if strict:
                raise StockfishEngineError(f"Error during Stockfish analysis: {err}") from err
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AnalysisResult(
                fen=fen,
                side_to_move=side_to_move,
                best_move_uci=None,
                best_move_san=None,
                candidates=[],
                search_depth=0,
                analysis_time_ms=elapsed_ms,
                engine_status=EngineStatus.ERROR,
                engine_name="Stockfish",
            )

        # 5. Parse multipv analysis entries
        candidates: List[MoveCandidate] = []
        best_move_uci: Optional[str] = None
        best_move_san: Optional[str] = None
        total_nodes = 0
        actual_depth = search_depth

        for idx, entry in enumerate(infos, start=1):
            pv: List[chess.Move] = entry.get("pv", [])
            if not pv:
                continue

            first_move = pv[0]
            # Strict safety check: verify move legality on board
            if first_move not in board.legal_moves:
                continue

            san_move = board.san(first_move)
            uci_move = first_move.uci()
            is_best = (idx == 1)

            if is_best:
                best_move_uci = uci_move
                best_move_san = san_move

            # Evaluation score extraction
            score_obj = entry.get("score")
            eval_score = self._parse_engine_score(score_obj, board.turn)

            # Convert PV moves to UCI and SAN notation
            pv_uci = [m.uci() for m in pv]
            pv_san: List[str] = []
            temp_board = board.copy()
            for m in pv:
                if m in temp_board.legal_moves:
                    pv_san.append(temp_board.san(m))
                    temp_board.push(m)
                else:
                    break

            if "nodes" in entry:
                total_nodes += entry["nodes"]
            if "depth" in entry and entry["depth"] is not None:
                actual_depth = entry["depth"]

            candidate = MoveCandidate(
                rank=idx,
                uci=uci_move,
                san=san_move,
                evaluation=eval_score,
                pv_uci=pv_uci,
                pv_san=pv_san,
                is_best_move=is_best,
            )
            candidates.append(candidate)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Engine identifier
        engine_name = "Stockfish"
        if hasattr(self._engine, "id") and self._engine.id.get("name"):
            engine_name = self._engine.id["name"]

        return AnalysisResult(
            fen=fen,
            side_to_move=side_to_move,
            best_move_uci=best_move_uci,
            best_move_san=best_move_san,
            candidates=candidates,
            search_depth=actual_depth,
            analysis_time_ms=elapsed_ms,
            engine_status=EngineStatus.OK,
            engine_name=engine_name,
            nodes_evaluated=total_nodes if total_nodes > 0 else None,
            is_terminal=False,
        )

    @classmethod
    def _parse_engine_score(
        cls,
        score_obj: Optional[chess.engine.PovScore],
        turn: chess.Color,
    ) -> EvaluationScore:
        """Convert a chess.engine.PovScore into a normalized EvaluationScore."""
        if score_obj is None:
            return EvaluationScore(
                score_type=ScoreType.CENTIPAWN,
                value=0,
                score_relative_cp=0,
                score_white_cp=0,
                display_text="0.00",
            )

        # PovScore holds evaluation relative to the side to move by default
        relative_score = score_obj.relative
        white_score = score_obj.white()

        if relative_score.is_mate():
            mate_moves_rel = relative_score.mate()
            mate_moves_white = white_score.mate()
            disp = (
                f"+M{mate_moves_rel}"
                if mate_moves_rel and mate_moves_rel > 0
                else f"-M{abs(mate_moves_rel)}"
                if mate_moves_rel
                else "#"
            )
            return EvaluationScore(
                score_type=ScoreType.MATE,
                value=mate_moves_rel if mate_moves_rel is not None else 0,
                mate_in_relative=mate_moves_rel,
                mate_in_white=mate_moves_white,
                display_text=disp,
            )

        # Centipawn score
        cp_rel = relative_score.score() or 0
        cp_white = white_score.score() or 0
        disp_val = cp_rel / 100.0
        disp = f"+{disp_val:.2f}" if disp_val > 0 else f"{disp_val:.2f}"

        return EvaluationScore(
            score_type=ScoreType.CENTIPAWN,
            value=cp_rel,
            score_relative_cp=cp_rel,
            score_white_cp=cp_white,
            display_text=disp,
        )

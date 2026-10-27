"""ML Move Quality Predictor providing model inference and candidate move ranking."""

import os
import time
from typing import Any, Dict, List, Optional, Union
import chess
import joblib
import numpy as np

from backend.chess_engine import ChessEngine, IllegalMoveError, InvalidFENError
from backend.chess_engine.models import PieceColor
from backend.ml.preprocessing import MLPreprocessor
from backend.ml.schemas import (
    CandidateMovePrediction,
    MLAnalysisReport,
    MoveQualityTier,
    PredictionSource,
)


class ModelNotTrainedError(FileNotFoundError):
    """Raised when an inference request is made before the ML model has been trained."""

    def __init__(self, model_path: str) -> None:
        message = (
            f"No trained ML model found at '{model_path}'. "
            "Please train the model first using 'python -m backend.ml.train' "
            "or by calling 'backend.ml.train_pipeline()'."
        )
        super().__init__(message)
        self.model_path = model_path


class MLMoveQualityPredictor:
    """Predicts candidate move quality scores and rankings using a trained ML model."""

    DEFAULT_MODEL_PATH = os.path.join("models", "candidate_quality_model.joblib")

    def __init__(
        self,
        model_path: Optional[str] = None,
        autoload: bool = True,
    ) -> None:
        self.model_path = model_path or self.DEFAULT_MODEL_PATH
        self.model_bundle: Optional[Dict[str, Any]] = None
        self.model: Any = None
        self.scaler: Any = None
        self.feature_names: List[str] = []
        self.model_name: str = "Uninitialized"
        self.model_version: str = "0.0.0"

        if autoload and os.path.exists(self.model_path):
            self.load_model(self.model_path)

    @property
    def is_trained(self) -> bool:
        """Check if model bundle is currently loaded and ready for inference."""
        return self.model is not None and self.scaler is not None and len(self.feature_names) > 0

    def load_model(self, model_path: str) -> None:
        """Safely load trained model bundle containing estimator, scaler, and feature schema."""
        if not os.path.exists(model_path):
            raise ModelNotTrainedError(model_path)

        bundle = joblib.load(model_path)
        if not isinstance(bundle, dict) or "model" not in bundle or "scaler" not in bundle:
            raise ValueError(f"Invalid model bundle format at '{model_path}'")

        self.model_bundle = bundle
        self.model = bundle["model"]
        self.scaler = bundle["scaler"]
        self.feature_names = bundle["feature_names"]
        self.model_name = bundle.get("model_name", "Unknown ML Model")
        self.model_version = bundle.get("model_version", "1.0.0")
        self.model_path = model_path

    def predict_move_quality(
        self,
        fen_or_engine: Union[str, ChessEngine],
        candidate_moves: Optional[List[Union[str, chess.Move]]] = None,
    ) -> MLAnalysisReport:
        """Predict the quality of candidate moves from a given position.

        Args:
            fen_or_engine: FEN string or ChessEngine instance.
            candidate_moves: List of candidate moves (UCI/SAN/Move). If None, all legal moves.

        Returns:
            MLAnalysisReport with ranked candidate moves and quality probabilities.

        Raises:
            ModelNotTrainedError: If model has not been trained or loaded yet.
            IllegalMoveError: If any candidate move is illegal in the current position.
        """
        if not self.is_trained:
            # Try to load if file appeared since initialization
            if os.path.exists(self.model_path):
                self.load_model(self.model_path)
            else:
                raise ModelNotTrainedError(self.model_path)

        start_time = time.perf_counter()

        if isinstance(fen_or_engine, ChessEngine):
            engine = fen_or_engine
        else:
            try:
                engine = ChessEngine(str(fen_or_engine))
            except Exception as err:
                raise InvalidFENError(str(fen_or_engine), reason=str(err)) from err

        board = engine.board
        active_color = engine.turn

        # Validate and parse candidate moves
        if candidate_moves is None or len(candidate_moves) == 0:
            moves_to_evaluate = list(board.legal_moves)
        else:
            moves_to_evaluate = []
            for m in candidate_moves:
                parsed_move = engine.parse_move(m)
                if parsed_move not in board.legal_moves:
                    raise IllegalMoveError(
                        move_str=str(m),
                        fen=engine.fen,
                        reason="Candidate move is illegal in current position",
                    )
                moves_to_evaluate.append(parsed_move)

        if not moves_to_evaluate:
            inference_ms = (time.perf_counter() - start_time) * 1000
            return MLAnalysisReport(
                fen=engine.fen,
                side_to_move=active_color,
                model_name=self.model_name,
                model_version=self.model_version,
                candidates=[],
                best_move_uci=None,
                best_move_san=None,
                inference_time_ms=inference_ms,
                total_candidates_evaluated=0,
            )

        # 1. Transform moves using EXACT scaler and feature order from training
        X_scaled = MLPreprocessor.transform_single_position(
            board=board,
            moves=moves_to_evaluate,
            feature_names=self.feature_names,
            scaler=self.scaler,
        )

        # 2. Predict probabilities / scores
        if hasattr(self.model, "predict_proba"):
            scores = self.model.predict_proba(X_scaled)[:, 1]
        elif hasattr(self.model, "decision_function"):
            raw_scores = self.model.decision_function(X_scaled)
            scores = 1.0 / (1.0 + np.exp(-raw_scores))
        else:
            scores = self.model.predict(X_scaled).astype(float)

        # 3. Assemble candidate predictions
        candidates: List[CandidateMovePrediction] = []
        for idx, (move, score) in enumerate(zip(moves_to_evaluate, scores)):
            tier = self._assign_quality_tier(score)
            is_cap = board.is_capture(move)
            is_chk = board.gives_check(move)
            is_promo = move.promotion is not None
            is_cast = board.is_castling(move)

            highlights = {
                "moving_piece": chess.piece_name(board.piece_at(move.from_square).piece_type) if board.piece_at(move.from_square) else "unknown",
                "is_capture": is_cap,
                "is_check": is_chk,
            }

            candidates.append(
                CandidateMovePrediction(
                    move_uci=move.uci(),
                    move_san=board.san(move),
                    rank=0,  # Assigned after sorting
                    quality_score=float(score),
                    quality_tier=tier,
                    is_top_recommendation=False,
                    is_capture=is_cap,
                    is_check=is_chk,
                    is_promotion=is_promo,
                    is_castling=is_cast,
                    feature_highlights=highlights,
                    source=PredictionSource.MACHINE_LEARNING,
                )
            )

        # 4. Sort candidates by score descending
        candidates.sort(key=lambda c: c.quality_score, reverse=True)
        for rank_idx, c in enumerate(candidates, start=1):
            c.rank = rank_idx

        if candidates:
            candidates[0].is_top_recommendation = True
            best_uci = candidates[0].move_uci
            best_san = candidates[0].move_san
        else:
            best_uci = None
            best_san = None

        inference_ms = (time.perf_counter() - start_time) * 1000

        return MLAnalysisReport(
            fen=engine.fen,
            side_to_move=active_color,
            model_name=self.model_name,
            model_version=self.model_version,
            candidates=candidates,
            best_move_uci=best_uci,
            best_move_san=best_san,
            inference_time_ms=inference_ms,
            total_candidates_evaluated=len(candidates),
        )

    @staticmethod
    def _assign_quality_tier(score: float) -> MoveQualityTier:
        """Classify continuous predicted score into a human-understandable quality tier."""
        if score >= 0.70:
            return MoveQualityTier.EXCELLENT
        if score >= 0.50:
            return MoveQualityTier.GOOD
        if score >= 0.35:
            return MoveQualityTier.INACCURACY
        if score >= 0.20:
            return MoveQualityTier.MISTAKE
        return MoveQualityTier.BLUNDER

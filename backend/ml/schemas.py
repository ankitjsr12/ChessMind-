"""Data schemas and transfer objects for Module 4: Candidate Move Quality Prediction."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import chess

from backend.chess_engine.models import PieceColor


class MoveQualityTier(str, Enum):
    """Categorical classification of move quality."""
    EXCELLENT = "excellent"     # Best move or essentially equal to best
    GOOD = "good"               # Solid move with minimal concession
    INACCURACY = "inaccuracy"   # Minor mistake or suboptimal move
    MISTAKE = "mistake"         # Significant drop in position quality
    BLUNDER = "blunder"         # Game-losing error or severe material blunder


class PredictionSource(str, Enum):
    """Source indicator clearly separating ML predictions from engine calculations."""
    MACHINE_LEARNING = "machine_learning"
    STOCKFISH_ENGINE = "stockfish_engine"
    MINIMAX_SEARCH = "minimax_search"


@dataclass
class CandidateMovePrediction:
    """Predicted quality metrics for a single candidate chess move."""
    move_uci: str
    move_san: str
    rank: int
    quality_score: float             # Continuous predicted probability/score [0.0, 1.0]
    quality_tier: MoveQualityTier    # Categorical classification
    is_top_recommendation: bool
    is_capture: bool
    is_check: bool
    is_promotion: bool
    is_castling: bool
    feature_highlights: Dict[str, Any] = field(default_factory=dict)
    source: PredictionSource = PredictionSource.MACHINE_LEARNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert prediction to JSON-serializable dictionary."""
        return {
            "move_uci": self.move_uci,
            "move_san": self.move_san,
            "rank": self.rank,
            "quality_score": round(self.quality_score, 4),
            "quality_tier": self.quality_tier.value,
            "is_top_recommendation": self.is_top_recommendation,
            "is_capture": self.is_capture,
            "is_check": self.is_check,
            "is_promotion": self.is_promotion,
            "is_castling": self.is_castling,
            "feature_highlights": self.feature_highlights,
            "source": self.source.value,
        }


@dataclass
class MLAnalysisReport:
    """Comprehensive analysis report for a position evaluated by the ML model."""
    fen: str
    side_to_move: PieceColor
    model_name: str
    model_version: str
    candidates: List[CandidateMovePrediction]
    best_move_uci: Optional[str]
    best_move_san: Optional[str]
    inference_time_ms: float
    total_candidates_evaluated: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialize analysis report to structured dictionary."""
        return {
            "fen": self.fen,
            "side_to_move": self.side_to_move.value,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "best_move": {
                "uci": self.best_move_uci,
                "san": self.best_move_san,
            } if self.best_move_uci else None,
            "total_candidates_evaluated": self.total_candidates_evaluated,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "candidates": [c.to_dict() for c in self.candidates],
        }


@dataclass
class TrainingConfig:
    """Configuration settings for dataset creation, preprocessing, and training."""
    dataset_name: str = "lichess_public_domain_master_games"
    dataset_version: str = "1.0.0"
    random_seed: int = 42
    test_size: float = 0.20
    max_games: int = 100
    max_positions_per_game: int = 20
    candidate_alternatives_per_pos: int = 4
    model_output_dir: str = "models"
    model_filename: str = "candidate_quality_model.joblib"
    artifacts_output_dir: str = "artifacts"
    models_to_train: List[str] = field(default_factory=lambda: ["logistic_regression", "random_forest", "xgboost"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "random_seed": self.random_seed,
            "test_size": self.test_size,
            "max_games": self.max_games,
            "max_positions_per_game": self.max_positions_per_game,
            "candidate_alternatives_per_pos": self.candidate_alternatives_per_pos,
            "model_output_dir": self.model_output_dir,
            "model_filename": self.model_filename,
            "artifacts_output_dir": self.artifacts_output_dir,
            "models_to_train": self.models_to_train,
        }


@dataclass
class ModelEvaluationMetrics:
    """Evaluation metrics for a trained candidate move model."""
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: Optional[float]
    top1_move_accuracy: float   # Top-1 candidate ranking match rate
    top3_move_accuracy: float   # Top-3 candidate ranking match rate
    mrr: float                  # Mean Reciprocal Rank
    brier_score: float          # Calibration metric
    class_imbalance_ratio: float
    confusion_matrix: List[List[int]]
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "roc_auc": round(self.roc_auc, 4) if self.roc_auc is not None else None,
            "top1_move_accuracy": round(self.top1_move_accuracy, 4),
            "top3_move_accuracy": round(self.top3_move_accuracy, 4),
            "mrr": round(self.mrr, 4),
            "brier_score": round(self.brier_score, 4),
            "class_imbalance_ratio": round(self.class_imbalance_ratio, 4),
            "confusion_matrix": self.confusion_matrix,
            "sample_count": self.sample_count,
        }

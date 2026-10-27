"""Module 5: Neural Chess Position Evaluation for ChessMind AI.

Technology: PyTorch, NumPy, python-chess.
"""

import os

# Prevent OpenMP runtime deadlocks between PyTorch and XGBoost on macOS
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from backend.deep_learning.board_encoder import BoardEncoder, BOARD_SIZE, TOTAL_PLANES
from backend.deep_learning.dataset import ChessPositionDataset, DeepLearningDataPipeline
from backend.deep_learning.evaluate import NeuralEvaluatorBenchmark
from backend.deep_learning.inference import (
    NeuralModelNotTrainedError,
    NeuralPositionEvaluator,
)
from backend.deep_learning.model import (
    ChessCNNEvaluator,
    ChessMLPEvaluator,
    cp_to_target,
    create_neural_model,
    target_to_cp,
)
from backend.deep_learning.train import get_optimal_device, train_neural_evaluator

__all__ = [
    "BoardEncoder",
    "TOTAL_PLANES",
    "BOARD_SIZE",
    "ChessMLPEvaluator",
    "ChessCNNEvaluator",
    "create_neural_model",
    "cp_to_target",
    "target_to_cp",
    "ChessPositionDataset",
    "DeepLearningDataPipeline",
    "train_neural_evaluator",
    "get_optimal_device",
    "NeuralEvaluatorBenchmark",
    "NeuralPositionEvaluator",
    "NeuralModelNotTrainedError",
]

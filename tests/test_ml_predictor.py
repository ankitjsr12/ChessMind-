"""Unit and integration tests for Module 4: Candidate Move Quality Prediction."""

import os
import tempfile
import pytest
import chess
import numpy as np
import pandas as pd

from backend.chess_engine import ChessEngine, IllegalMoveError
from backend.chess_engine.models import PieceColor
from backend.ml import (
    CandidateMovePrediction,
    ChessDataLoader,
    ChessFeatureExtractor,
    MLAnalysisReport,
    MLMoveQualityPredictor,
    MLPreprocessor,
    ModelEvaluationMetrics,
    ModelNotTrainedError,
    MoveQualityTier,
    PredictionSource,
    TrainingConfig,
    train_pipeline,
)

STARTING_FEN = chess.STARTING_FEN
TACTICAL_FEN = "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"


class TestChessDataLoader:
    """Test suite for PGN parsing and dataset generation."""

    def test_load_sample_dataset(self) -> None:
        loader = ChessDataLoader(max_positions_per_game=5, candidate_alternatives_per_pos=3)
        df = loader.load_sample_dataset(max_games=3)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        required_cols = ["game_id", "ply", "fen", "turn", "move_uci", "move_san", "is_played_move", "is_quality_move"]
        for col in required_cols:
            assert col in df.columns

        # Verify positive and negative candidate examples exist
        assert (df["is_quality_move"] == 1).sum() > 0
        assert (df["is_quality_move"] == 0).sum() > 0


class TestMLPreprocessing:
    """Test suite for feature matrix assembly and leakage-safe group splitting."""

    def test_leakage_free_group_split(self) -> None:
        loader = ChessDataLoader(max_positions_per_game=4, candidate_alternatives_per_pos=2)
        df_raw = loader.load_sample_dataset(max_games=4)

        preprocessor = MLPreprocessor(random_state=42)
        df_featured = preprocessor.build_feature_dataframe(df_raw)

        dataset = preprocessor.prepare_train_test_split(df_featured, test_size=0.25)

        # CRITICAL TEST: Zero overlap between train games and test games
        train_games_set = set(dataset.train_games)
        test_games_set = set(dataset.test_games)
        overlap = train_games_set.intersection(test_games_set)
        assert len(overlap) == 0, f"Data leakage detected! Overlapping games: {overlap}"

        # Scaled arrays shape check
        assert dataset.X_train.shape[1] == len(dataset.feature_names)
        assert dataset.X_test.shape[1] == len(dataset.feature_names)
        assert len(dataset.y_train) == dataset.X_train.shape[0]
        assert len(dataset.y_test) == dataset.X_test.shape[0]


class TestTrainingPipeline:
    """Test suite for training pipeline, model persistence, and evaluation reports."""

    def test_train_pipeline_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "models")
            artifacts_dir = os.path.join(tmpdir, "artifacts")

            config = TrainingConfig(
                max_games=4,
                max_positions_per_game=4,
                candidate_alternatives_per_pos=2,
                test_size=0.25,
                model_output_dir=model_dir,
                artifacts_output_dir=artifacts_dir,
                models_to_train=["logistic_regression", "random_forest", "xgboost"],
                random_seed=42,
            )

            bundle, metrics_list = train_pipeline(config=config)

            # Check model bundle contents
            assert "model" in bundle
            assert "scaler" in bundle
            assert "feature_names" in bundle
            assert "model_name" in bundle
            assert len(metrics_list) == 3

            # Check saved checkpoint
            saved_model_file = os.path.join(model_dir, "candidate_quality_model.joblib")
            assert os.path.exists(saved_model_file)

            # Check saved reports
            assert os.path.exists(os.path.join(artifacts_dir, "training_report.json"))
            assert os.path.exists(os.path.join(artifacts_dir, "evaluation_report.md"))


class TestMLPredictor:
    """Test suite for ML Move Quality Predictor inference."""

    def test_model_not_trained_error(self) -> None:
        predictor = MLMoveQualityPredictor(model_path="non_existent_path.joblib", autoload=False)
        with pytest.raises(ModelNotTrainedError) as exc_info:
            predictor.predict_move_quality(STARTING_FEN)
        assert "No trained ML model found" in str(exc_info.value)

    def test_prediction_with_trained_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "models")
            config = TrainingConfig(
                max_games=4,
                max_positions_per_game=4,
                candidate_alternatives_per_pos=2,
                model_output_dir=model_dir,
                models_to_train=["logistic_regression"],
                random_seed=42,
            )
            train_pipeline(config=config)

            model_path = os.path.join(model_dir, "candidate_quality_model.joblib")
            predictor = MLMoveQualityPredictor(model_path=model_path)

            candidates = ["e2e4", "d2d4", "g1f3", "a2a3"]
            report = predictor.predict_move_quality(STARTING_FEN, candidate_moves=candidates)

            assert isinstance(report, MLAnalysisReport)
            assert report.side_to_move == PieceColor.WHITE
            assert len(report.candidates) == 4
            assert report.total_candidates_evaluated == 4
            assert report.best_move_uci in candidates

            # Verify predictions are sorted descending by quality_score
            scores = [c.quality_score for c in report.candidates]
            assert scores == sorted(scores, reverse=True)

            # Verify score ranges
            for c in report.candidates:
                assert isinstance(c, CandidateMovePrediction)
                assert 0.0 <= c.quality_score <= 1.0
                assert isinstance(c.quality_tier, MoveQualityTier)
                assert c.source == PredictionSource.MACHINE_LEARNING

    def test_illegal_candidate_move_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "models")
            config = TrainingConfig(
                max_games=3,
                max_positions_per_game=3,
                model_output_dir=model_dir,
                models_to_train=["logistic_regression"],
                random_seed=42,
            )
            train_pipeline(config=config)
            predictor = MLMoveQualityPredictor(model_path=os.path.join(model_dir, "candidate_quality_model.joblib"))

            with pytest.raises(IllegalMoveError):
                predictor.predict_move_quality(STARTING_FEN, candidate_moves=["e2e5"])

    def test_report_json_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "models")
            config = TrainingConfig(
                max_games=3,
                max_positions_per_game=3,
                model_output_dir=model_dir,
                models_to_train=["logistic_regression"],
                random_seed=42,
            )
            train_pipeline(config=config)
            predictor = MLMoveQualityPredictor(model_path=os.path.join(model_dir, "candidate_quality_model.joblib"))

            report = predictor.predict_move_quality(STARTING_FEN, candidate_moves=["e4", "d4"])
            data = report.to_dict()

            assert "fen" in data
            assert "side_to_move" in data
            assert "model_name" in data
            assert "candidates" in data
            assert len(data["candidates"]) == 2
            assert data["candidates"][0]["source"] == "machine_learning"

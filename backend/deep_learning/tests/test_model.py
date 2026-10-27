"""Unit and integration tests for Neural Models and Evaluator (Module 5)."""

import os
import tempfile
import pytest
import chess
import torch

from backend.chess_engine import IllegalMoveError
from backend.deep_learning import (
    BoardEncoder,
    ChessCNNEvaluator,
    ChessMLPEvaluator,
    NeuralEvaluatorBenchmark,
    NeuralModelNotTrainedError,
    NeuralPositionEvaluator,
    cp_to_target,
    create_neural_model,
    target_to_cp,
    train_neural_evaluator,
)

STARTING_FEN = chess.STARTING_FEN
TACTICAL_FEN = "r1bqk2r/pppp1ppp/2n5/4p3/1b2P3/2NP1N2/PPPB1PPP/R2QKB1R w KQkq - 0 6"


class TestNeuralModels:
    """Test suite for PyTorch architectures, dimensions, and target conversion."""

    def test_mlp_model_forward_pass(self) -> None:
        model = ChessMLPEvaluator()
        batch_x = torch.randn(4, 18, 8, 8)
        output = model(batch_x)

        assert output.shape == (4,)
        # Output bounded by Tanh in [-1.0, 1.0]
        assert (output >= -1.0).all() and (output <= 1.0).all()

    def test_cnn_model_forward_pass(self) -> None:
        model = ChessCNNEvaluator(in_channels=18, conv_channels=32, res_blocks=1)
        batch_x = torch.randn(4, 18, 8, 8)
        output = model(batch_x)

        assert output.shape == (4,)
        assert (output >= -1.0).all() and (output <= 1.0).all()

    def test_model_factory(self) -> None:
        mlp = create_neural_model("mlp")
        assert isinstance(mlp, ChessMLPEvaluator)

        cnn = create_neural_model("cnn")
        assert isinstance(cnn, ChessCNNEvaluator)

        with pytest.raises(ValueError):
            create_neural_model("transformer_invalid")

    def test_cp_target_conversion_roundtrip(self) -> None:
        cps = [0.0, 150.0, -250.0, 500.0, -800.0]
        for cp in cps:
            target = cp_to_target(cp, scale=400.0)
            assert -1.0 <= target <= 1.0
            reconstructed_cp = target_to_cp(target, scale=400.0)
            assert abs(cp - reconstructed_cp) < 0.1


class TestNeuralTrainingAndInference:
    """End-to-end integration tests for neural training, inference, and benchmarking."""

    def test_neural_model_not_trained_error(self) -> None:
        evaluator = NeuralPositionEvaluator(checkpoint_path="non_existent_weights.pt", autoload=False)
        with pytest.raises(NeuralModelNotTrainedError) as exc_info:
            evaluator.evaluate_position(STARTING_FEN)
        assert "No trained neural model found" in str(exc_info.value)

    def test_small_end_to_end_training_and_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "models", "neural", "test_cnn.pt")

            # 1. Train small model for 2 epochs on 3 games
            model, summary = train_neural_evaluator(
                model_type="cnn",
                epochs=2,
                batch_size=8,
                max_games=3,
                model_output_path=model_path,
                random_seed=42,
            )

            assert os.path.exists(model_path)
            assert summary["best_epoch"] >= 1
            assert len(summary["history"]) == 2

            # 2. Evaluate with NeuralPositionEvaluator
            evaluator = NeuralPositionEvaluator(checkpoint_path=model_path)
            assert evaluator.is_trained is True

            # Position evaluation
            res = evaluator.evaluate_position(STARTING_FEN)
            assert "eval_white_cp" in res
            assert "eval_relative_cp" in res
            assert "white_win_probability" in res
            assert 0.0 <= res["white_win_probability"] <= 1.0
            assert res["source"] == "neural_network"

            # Candidate move ranking
            candidates = ["e2e4", "d2d4", "g1f3"]
            ranked_moves = evaluator.evaluate_candidate_moves(STARTING_FEN, candidate_moves=candidates)
            assert len(ranked_moves) == 3
            assert ranked_moves[0]["rank"] == 1
            assert ranked_moves[1]["rank"] == 2
            assert ranked_moves[2]["rank"] == 3
            # Checked that all moves are from candidate list
            for rm in ranked_moves:
                assert rm["move_uci"] in candidates
                assert "post_move_eval_player_cp" in rm

            # Illegal candidate move handling
            with pytest.raises(IllegalMoveError):
                evaluator.evaluate_candidate_moves(STARTING_FEN, candidate_moves=["e2e5"])

            # 3. Benchmark on test set
            test_records = summary["test_records"]
            if test_records:
                bench_metrics = NeuralEvaluatorBenchmark.evaluate_test_set(model, test_records)
                assert "neural_network" in bench_metrics
                assert "material_baseline" in bench_metrics
                assert "mae_centipawns" in bench_metrics["neural_network"]
                md_report = NeuralEvaluatorBenchmark.generate_markdown_report(bench_metrics, model_type="cnn")
                assert "# Module 5: Neural Chess Position Evaluation Benchmark" in md_report

"""Unit and Integration Tests for Module 2: Best Move Predictor."""

from typing import List
from unittest.mock import MagicMock, patch
import pytest
import chess
import chess.engine

from backend.chess_engine import ChessEngine, InvalidFENError
from backend.chess_engine.models import BaseMovePredictor, PieceColor
from backend.predictor import (
    AnalysisResult,
    AnalysisTimeoutError,
    ComparisonResult,
    EngineStatus,
    EvaluationScore,
    MinimaxEngine,
    MoveCandidate,
    MoveRanker,
    ScoreType,
    StockfishEngineError,
    StockfishNotFoundError,
    StockfishService,
)


# Test Positions
STARTING_FEN = chess.STARTING_FEN
MIDDLEGAME_FEN = "r1bq1rk1/ppp2ppp/2np1n2/1B2p3/1b2P3/2NP1N2/PPPB1PPP/R2QK2R w KQ - 0 7"
ENDGAME_FEN = "8/5k2/8/8/8/8/4K3/4R3 w - - 0 1"
CHECKMATE_FEN = "rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1"  # Fool's mate delivered
STALEMATE_FEN = "k7/8/1Q6/8/8/8/8/K7 b - - 0 1"
MATE_IN_ONE_FEN = "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"  # Qxf7#


class TestMinimaxEngine:
    """Tests for the Minimax + Alpha-Beta baseline engine."""

    def test_opening_analysis(self) -> None:
        engine = MinimaxEngine(default_depth=2)
        res = engine.analyze(STARTING_FEN, candidate_count=4)

        assert res.engine_status == EngineStatus.OK
        assert res.side_to_move == PieceColor.WHITE
        assert res.best_move_uci is not None
        assert res.best_move_san is not None
        assert len(res.candidates) == 4

        # Validate candidates are ranked and legal
        for idx, candidate in enumerate(res.candidates, start=1):
            assert candidate.rank == idx
            assert candidate.is_best_move == (idx == 1)
            assert candidate.uci is not None
            assert candidate.san is not None
            assert candidate.evaluation.score_type == ScoreType.CENTIPAWN
            assert len(candidate.pv_uci) > 0
            assert len(candidate.pv_san) > 0

    def test_middlegame_analysis(self) -> None:
        engine = MinimaxEngine(default_depth=2)
        res = engine.analyze(MIDDLEGAME_FEN, candidate_count=3)

        assert res.engine_status == EngineStatus.OK
        assert len(res.candidates) == 3
        assert res.search_depth == 2
        assert res.nodes_evaluated > 0
        assert res.analysis_time_ms >= 0

    def test_endgame_analysis(self) -> None:
        engine = MinimaxEngine(default_depth=2)
        res = engine.analyze(ENDGAME_FEN, candidate_count=3)

        assert res.engine_status == EngineStatus.OK
        assert res.best_move_uci is not None

    def test_black_turn_analysis(self) -> None:
        # Black to move position
        fen_black = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        engine = MinimaxEngine(default_depth=2)
        res = engine.analyze(fen_black, candidate_count=3)

        assert res.side_to_move == PieceColor.BLACK
        assert res.best_move_uci is not None
        # Relative score: from Black's perspective
        for cand in res.candidates:
            assert cand.evaluation.score_relative_cp is not None
            assert cand.evaluation.score_white_cp is not None
            # White score must be negation of Black's relative score
            assert cand.evaluation.score_white_cp == -cand.evaluation.score_relative_cp

    def test_mate_in_one_detection(self) -> None:
        engine = MinimaxEngine(default_depth=2)
        res = engine.analyze(MATE_IN_ONE_FEN, candidate_count=2)

        # White can play Qxf7#
        assert res.best_move_san == "Qxf7#"
        assert res.candidates[0].evaluation.score_type == ScoreType.MATE
        assert res.candidates[0].evaluation.mate_in_relative == 1

    def test_terminal_position_checkmate(self) -> None:
        engine = MinimaxEngine()
        res = engine.analyze(CHECKMATE_FEN)

        assert res.is_terminal is True
        assert res.engine_status == EngineStatus.TERMINAL_POSITION
        assert res.best_move_uci is None
        assert len(res.candidates) == 0
        assert "Checkmate" in (res.terminal_reason or "")

    def test_terminal_position_stalemate(self) -> None:
        engine = MinimaxEngine()
        res = engine.analyze(STALEMATE_FEN)

        assert res.is_terminal is True
        assert res.engine_status == EngineStatus.TERMINAL_POSITION
        assert res.best_move_uci is None
        assert len(res.candidates) == 0
        assert "Stalemate" in (res.terminal_reason or "")

    def test_invalid_fen_handling(self) -> None:
        engine = MinimaxEngine()
        with pytest.raises(InvalidFENError):
            engine.analyze("invalid fen string")


class TestStockfishService:
    """Tests for StockfishService process management and UCI parsing."""

    def test_find_stockfish_binary(self) -> None:
        # Even if not installed, find_stockfish_binary should return str or None without error
        path = StockfishService.find_stockfish_binary()
        assert path is None or isinstance(path, str)

    def test_stockfish_not_found_strict_mode(self) -> None:
        service = StockfishService(executable_path="/non/existent/stockfish/path")
        with pytest.raises(StockfishNotFoundError) as exc_info:
            service.analyze(STARTING_FEN, strict=True)
        assert "Stockfish executable not found" in str(exc_info.value)

    def test_stockfish_not_found_lenient_mode(self) -> None:
        service = StockfishService(executable_path="/non/existent/stockfish/path")
        res = service.analyze(STARTING_FEN, strict=False)
        assert res.engine_status == EngineStatus.NOT_AVAILABLE
        assert res.best_move_uci is None

    def test_terminal_position_checkmate_skips_process(self) -> None:
        # Should detect checkmate directly without launching process
        service = StockfishService(executable_path="/non/existent/stockfish/path")
        res = service.analyze(CHECKMATE_FEN, strict=True)
        assert res.is_terminal is True
        assert res.engine_status == EngineStatus.TERMINAL_POSITION
        assert "Checkmate" in (res.terminal_reason or "")

    def test_terminal_position_stalemate_skips_process(self) -> None:
        service = StockfishService(executable_path="/non/existent/stockfish/path")
        res = service.analyze(STALEMATE_FEN, strict=True)
        assert res.is_terminal is True
        assert res.engine_status == EngineStatus.TERMINAL_POSITION
        assert "Stalemate" in (res.terminal_reason or "")

    def test_mock_stockfish_multipv_analysis(self) -> None:
        """Test UCI multipv response parsing with a mock SimpleEngine."""
        mock_engine = MagicMock(spec=chess.engine.SimpleEngine)
        mock_engine.id = {"name": "Stockfish 16 Mock"}

        # Simulate multipv analysis output for 1. e4 and 1. d4
        mock_infos = [
            {
                "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
                "score": chess.engine.PovScore(chess.engine.Cp(35), chess.WHITE),
                "depth": 15,
                "nodes": 125000,
            },
            {
                "pv": [chess.Move.from_uci("d2d4"), chess.Move.from_uci("d7d5")],
                "score": chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE),
                "depth": 15,
                "nodes": 98000,
            },
            {
                "pv": [chess.Move.from_uci("g1f3"), chess.Move.from_uci("g8f6")],
                "score": chess.engine.PovScore(chess.engine.Cp(18), chess.WHITE),
                "depth": 15,
                "nodes": 85000,
            },
            {
                "pv": [chess.Move.from_uci("c2c4"), chess.Move.from_uci("e7e6")],
                "score": chess.engine.PovScore(chess.engine.Cp(12), chess.WHITE),
                "depth": 15,
                "nodes": 72000,
            },
        ]
        mock_engine.analyse.return_value = mock_infos

        service = StockfishService(engine_instance=mock_engine)
        res = service.analyze(STARTING_FEN, depth=15, multipv=4)

        assert res.engine_status == EngineStatus.OK
        assert res.best_move_uci == "e2e4"
        assert res.best_move_san == "e4"
        assert len(res.candidates) == 4
        assert res.search_depth == 15
        assert res.nodes_evaluated == sum([e["nodes"] for e in mock_infos])

        # Verify candidate ranking and evaluations
        rank1 = res.candidates[0]
        assert rank1.rank == 1
        assert rank1.is_best_move is True
        assert rank1.san == "e4"
        assert rank1.evaluation.score_type == ScoreType.CENTIPAWN
        assert rank1.evaluation.score_relative_cp == 35
        assert rank1.evaluation.score_white_cp == 35
        assert rank1.evaluation.display_text == "+0.35"
        assert rank1.pv_san == ["e4", "e5"]

        rank2 = res.candidates[1]
        assert rank2.rank == 2
        assert rank2.is_best_move is False
        assert rank2.san == "d4"

    def test_mock_forced_mate_score(self) -> None:
        """Test forced checkmate score handling."""
        mock_engine = MagicMock(spec=chess.engine.SimpleEngine)
        mock_engine.id = {"name": "Stockfish Mock"}

        mock_infos = [
            {
                "pv": [chess.Move.from_uci("h5f7")],
                "score": chess.engine.PovScore(chess.engine.Mate(1), chess.WHITE),
                "depth": 10,
                "nodes": 5000,
            }
        ]
        mock_engine.analyse.return_value = mock_infos

        service = StockfishService(engine_instance=mock_engine)
        res = service.analyze(MATE_IN_ONE_FEN, depth=10)

        assert res.best_move_san == "Qxf7#"
        candidate = res.candidates[0]
        assert candidate.evaluation.score_type == ScoreType.MATE
        assert candidate.evaluation.mate_in_relative == 1
        assert candidate.evaluation.mate_in_white == 1
        assert candidate.evaluation.display_text == "+M1"

    def test_context_manager_and_close(self) -> None:
        mock_engine = MagicMock(spec=chess.engine.SimpleEngine)
        service = StockfishService(engine_instance=mock_engine)
        with service as s:
            assert s.is_available() is True
        mock_engine.quit.assert_called_once()


class TestMoveRankerAndComparison:
    """Tests for MoveRanker orchestration, fallback, and comparison interface."""

    def test_move_ranker_fallback_to_minimax(self) -> None:
        # Stockfish unavailable: should fall back to Minimax seamlessly
        unavailable_stockfish = StockfishService(executable_path="/non/existent/path")
        ranker = MoveRanker(stockfish_service=unavailable_stockfish)

        res = ranker.predict_best_moves(STARTING_FEN, candidate_count=4, fallback_to_minimax=True)
        assert res.engine_status == EngineStatus.OK
        assert "Fallback" in res.engine_name
        assert len(res.candidates) == 4
        assert res.best_move_uci is not None

    def test_move_ranker_no_fallback_raises(self) -> None:
        unavailable_stockfish = StockfishService(executable_path="/non/existent/path")
        ranker = MoveRanker(stockfish_service=unavailable_stockfish)

        with pytest.raises(StockfishNotFoundError):
            ranker.predict_best_moves(STARTING_FEN, fallback_to_minimax=False)

    def test_move_ranker_implements_base_move_predictor(self) -> None:
        ranker = MoveRanker()
        # Verify protocol compliance with Module 1
        assert isinstance(ranker, BaseMovePredictor)

        legal_moves = ["e2e4", "d2d4", "g1f3"]
        predicted = ranker.predict_move(STARTING_FEN, legal_moves)
        assert predicted in legal_moves

    def test_chess_engine_integration_play_ai_move(self) -> None:
        """Verify seamless integration with Module 1 ChessEngine.play_ai_move()."""
        engine = ChessEngine()
        ranker = MoveRanker()

        move_res = engine.play_ai_move(ranker)
        assert move_res.move_record.turn == PieceColor.WHITE
        assert len(engine.get_move_history()) == 1
        assert engine.turn == PieceColor.BLACK

    def test_compare_stockfish_and_minimax_interface(self) -> None:
        # Mock Stockfish service
        mock_engine = MagicMock(spec=chess.engine.SimpleEngine)
        mock_infos = [
            {
                "pv": [chess.Move.from_uci("g1f3"), chess.Move.from_uci("g8f6")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
                "depth": 10,
                "nodes": 10000,
            }
        ]
        mock_engine.analyse.return_value = mock_infos
        sf_service = StockfishService(engine_instance=mock_engine)

        ranker = MoveRanker(stockfish_service=sf_service)
        comparison = ranker.compare_stockfish_and_minimax(STARTING_FEN, candidate_count=2)

        assert isinstance(comparison, ComparisonResult)
        assert comparison.stockfish_analysis is not None
        assert comparison.minimax_analysis is not None
        assert isinstance(comparison.agreement, bool)
        assert len(comparison.summary) > 0

    def test_output_json_serialization_format(self) -> None:
        """Verify structured JSON output contains all user-required fields."""
        ranker = MoveRanker()
        res = ranker.predict_best_moves(STARTING_FEN, candidate_count=3)
        data = res.to_dict()

        # Required fields check
        assert "fen" in data
        assert "side_to_move" in data
        assert "best_move" in data
        assert "uci" in data["best_move"]
        assert "san" in data["best_move"]
        assert "candidate_moves" in data
        assert len(data["candidate_moves"]) == 3
        assert "search_depth" in data
        assert "analysis_time_ms" in data
        assert "engine_status" in data
        assert "disclaimer" in data

        # Candidate move fields check
        cand0 = data["candidate_moves"][0]
        assert "rank" in cand0
        assert "uci" in cand0
        assert "san" in cand0
        assert "evaluation" in cand0
        assert "score_type" in cand0["evaluation"]
        assert "display_text" in cand0["evaluation"]
        assert "pv_uci" in cand0
        assert "pv_san" in cand0


# ==============================================================================
# Module 4: Machine Learning Candidate Move Quality Predictor Tests
# ==============================================================================
import os
import tempfile
from backend.ml import (
    CandidateMovePrediction,
    MLAnalysisReport,
    MLMoveQualityPredictor,
    ModelNotTrainedError,
    MoveQualityTier,
    PredictionSource,
    TrainingConfig,
    train_pipeline,
)
from backend.chess_engine import IllegalMoveError


class TestMLCandidateMoveQuality:
    """Test suite for Module 4 Machine Learning Move Quality Predictor."""

    def test_ml_model_not_trained_error(self) -> None:
        predictor = MLMoveQualityPredictor(model_path="non_existent_file.joblib", autoload=False)
        with pytest.raises(ModelNotTrainedError) as exc_info:
            predictor.predict_move_quality(STARTING_FEN)
        assert "No trained ML model found" in str(exc_info.value)

    def test_ml_candidate_move_ranking(self) -> None:
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

            model_path = os.path.join(model_dir, "candidate_quality_model.joblib")
            predictor = MLMoveQualityPredictor(model_path=model_path)

            candidates = ["e2e4", "d2d4", "g1f3", "a2a3"]
            report = predictor.predict_move_quality(STARTING_FEN, candidate_moves=candidates)

            assert isinstance(report, MLAnalysisReport)
            assert report.side_to_move == PieceColor.WHITE
            assert len(report.candidates) == 4
            assert report.best_move_uci in candidates

            # Verify predictions are sorted descending by quality_score
            scores = [c.quality_score for c in report.candidates]
            assert scores == sorted(scores, reverse=True)

            for c in report.candidates:
                assert isinstance(c, CandidateMovePrediction)
                assert 0.0 <= c.quality_score <= 1.0
                assert isinstance(c.quality_tier, MoveQualityTier)
                assert c.source == PredictionSource.MACHINE_LEARNING

    def test_ml_illegal_candidate_raises(self) -> None:
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


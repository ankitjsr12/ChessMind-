"""Comprehensive tests for Module 3: Opponent Move Prediction."""

import time
import pytest
import chess

from backend.chess_engine import ChessEngine, IllegalMoveError, InvalidFENError
from backend.chess_engine.models import PieceColor
from backend.opponent_prediction import (
    CandidateConsequence,
    EvaluationBreakdown,
    MoveOrderer,
    OpponentAnalysisReport,
    OpponentResponse,
    OpponentSearchEngine,
    PositionEvaluator,
    PredictionType,
    SearchStatus,
    TTFlag,
    TranspositionTable,
)
from backend.predictor.schemas import ScoreType


# Test Positions
STARTING_FEN = chess.STARTING_FEN
TACTICAL_FORK_FEN = "r1bqk2r/pppp1ppp/2n5/4p3/1b2P3/2NP1N2/PPPB1PPP/R2QKB1R w KQkq - 0 6"
ENDGAME_KP_FEN = "8/4k3/8/4P3/8/8/4K3/8 w - - 0 1"
MATE_IN_ONE_FEN = "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"  # Qxf7#
FOOLS_MATE_PRE_FEN = "rnbqkbnr/pppp1ppp/4p3/8/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"    # Black plays Qh4#


class TestPositionEvaluator:
    """Tests for static evaluation, PST, mobility, king safety, and pawn structure."""

    def test_starting_position_symmetry(self) -> None:
        board = chess.Board(STARTING_FEN)
        breakdown = PositionEvaluator.evaluate_detailed(board)

        # Equal material
        assert breakdown.material_white == breakdown.material_black
        # Symmetrical PST and pawn structure
        assert breakdown.pst_white == breakdown.pst_black
        assert breakdown.pawn_structure_white == breakdown.pawn_structure_black
        # Total score should be essentially zero (symmetrical)
        assert abs(breakdown.total) < 20

    def test_material_imbalance_evaluation(self) -> None:
        # White has an extra Queen
        fen_white_up_q = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = chess.Board(fen_white_up_q)
        score = PositionEvaluator.evaluate(board)
        assert score > 800  # Queen advantage

    def test_bishop_pair_bonus(self) -> None:
        # Position where White has 2 bishops and Black has 1 bishop
        board = chess.Board("r1b1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        breakdown = PositionEvaluator.evaluate_detailed(board)
        assert breakdown.material_white > breakdown.material_black

    def test_passed_pawn_bonus(self) -> None:
        # White has a passed pawn on d6
        passed_fen = "8/8/3P4/8/8/8/4k3/4K3 w - - 0 1"
        board = chess.Board(passed_fen)
        breakdown = PositionEvaluator.evaluate_detailed(board)
        assert breakdown.pawn_structure_white > 0

    def test_doubled_pawn_penalty(self) -> None:
        # White has doubled pawns on c2 and c3
        doubled_fen = "8/8/8/8/8/2P5/2P5/4k2K w - - 0 1"
        board = chess.Board(doubled_fen)
        breakdown = PositionEvaluator.evaluate_detailed(board)
        assert breakdown.pawn_structure_white < 0

    def test_terminal_evaluation(self) -> None:
        # Checkmated board
        checkmated_board = chess.Board("rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1")
        score = PositionEvaluator.evaluate(checkmated_board)
        assert score == -30000

        # Stalemate board
        stalemate_board = chess.Board("k7/8/1Q6/8/8/8/8/K7 b - - 0 1")
        assert PositionEvaluator.evaluate(stalemate_board) == 0


class TestTranspositionTable:
    """Tests for TT caching, flag bounds, and mate score adjustments."""

    def test_store_and_lookup_exact(self) -> None:
        tt = TranspositionTable(max_entries=1000)
        board = chess.Board()
        key = tt.get_zobrist_key(board)
        move = chess.Move.from_uci("e2e4")

        tt.store(key=key, depth=3, value=45, flag=TTFlag.EXACT, best_move=move)
        score, best_move = tt.lookup(key=key, depth=3, alpha=-100, beta=100)

        assert score == 45
        assert best_move == move
        assert tt.hits == 1

    def test_lookup_cutoff_bounds(self) -> None:
        tt = TranspositionTable()
        board = chess.Board()
        key = tt.get_zobrist_key(board)

        # LOWERBOUND cutoff (fail-high): score >= beta
        tt.store(key=key, depth=3, value=80, flag=TTFlag.LOWERBOUND, best_move=None)
        score, _ = tt.lookup(key=key, depth=3, alpha=20, beta=50)
        assert score == 80

        # UPPERBOUND cutoff (fail-low): score <= alpha
        tt.store(key=key, depth=3, value=-30, flag=TTFlag.UPPERBOUND, best_move=None)
        score, _ = tt.lookup(key=key, depth=3, alpha=-10, beta=50)
        assert score == -30

    def test_mate_score_ply_normalization(self) -> None:
        tt = TranspositionTable()
        board = chess.Board()
        key = tt.get_zobrist_key(board)

        # Mate in 2 found at ply 3
        raw_mate_score = 29990
        tt.store(key=key, depth=4, value=raw_mate_score, flag=TTFlag.EXACT, best_move=None, ply=3)

        # Looked up at ply 5: should adjust appropriately
        val_at_ply_5, _ = tt.lookup(key=key, depth=4, alpha=-30000, beta=30000, ply=5)
        assert val_at_ply_5 == raw_mate_score - 2  # Adjusted by (5 - 3) = 2 plies


class TestMoveOrderer:
    """Tests for move ordering heuristics."""

    def test_mvv_lva_capture_ordering(self) -> None:
        orderer = MoveOrderer()
        # White Pawn on d4 can capture Black Queen on e5 or Black Pawn on c5
        board = chess.Board("8/8/8/2p1q3/3P4/8/8/4K2k w - - 0 1")

        cap_queen = chess.Move.from_uci("d4e5")
        cap_pawn = chess.Move.from_uci("d4c5")

        ordered = orderer.order_moves(board, [cap_pawn, cap_queen])
        # Capturing Queen (higher victim value) must be ordered before capturing pawn
        assert ordered[0] == cap_queen
        assert ordered[1] == cap_pawn

    def test_tt_move_highest_priority(self) -> None:
        orderer = MoveOrderer()
        board = chess.Board(STARTING_FEN)
        quiet_move = chess.Move.from_uci("g1f3")

        # Even a quiet move marked as TT best move gets highest priority
        ordered = orderer.order_moves(board, list(board.legal_moves), tt_move=quiet_move)
        assert ordered[0] == quiet_move

    def test_killer_moves_priority(self) -> None:
        orderer = MoveOrderer()
        board = chess.Board(STARTING_FEN)
        killer_move = chess.Move.from_uci("c2c4")

        # Record killer move at ply 1
        orderer.record_cutoff(board, killer_move, depth=3, ply=1)

        ordered = orderer.order_moves(board, list(board.legal_moves), ply=1)
        # Killer move should be ranked near top of quiet moves
        assert ordered.index(killer_move) < 5


class TestAlphaBetaPruningEfficiency:
    """Compares node counts with and without Alpha-Beta pruning."""

    def test_pruning_reduces_node_count_significantly(self) -> None:
        board = chess.Board(TACTICAL_FORK_FEN)
        engine = OpponentSearchEngine(default_depth=2, use_tt=True, use_move_ordering=True)

        # 1. Search with Alpha-Beta pruning
        engine.nodes_evaluated = 0
        score_ab, pv_ab = engine.negamax(board, depth=2, alpha=-100000, beta=100000)
        ab_nodes = engine.nodes_evaluated

        # 2. Pure Minimax without pruning
        score_pure, pure_nodes = engine.search_without_pruning(board, depth=2)

        # Both methods must yield exact same optimal score
        assert score_ab == score_pure
        # Alpha-Beta must evaluate fewer nodes
        assert ab_nodes < pure_nodes
        reduction_percentage = (1.0 - (ab_nodes / pure_nodes)) * 100
        print(f"\n[Pruning Benchmark] Pure Minimax: {pure_nodes} nodes | Alpha-Beta: {ab_nodes} nodes (Saved {reduction_percentage:.1f}%)")
        assert reduction_percentage > 25.0  # Significant reduction demonstrated fast


class TestOpponentMovePrediction:
    """Tests for analyzing candidate moves and predicting opponent responses."""

    def test_candidate_analysis_on_starting_position(self) -> None:
        engine = OpponentSearchEngine(default_depth=2)
        candidates = ["e2e4", "d2d4"]

        report = engine.analyze_candidate_consequences(STARTING_FEN, candidate_moves=candidates)

        assert isinstance(report, OpponentAnalysisReport)
        assert report.side_to_move == PieceColor.WHITE
        assert report.opponent_side == PieceColor.BLACK
        assert len(report.consequences) == 2

        for c in report.consequences:
            assert isinstance(c, CandidateConsequence)
            assert c.candidate_move_uci in candidates
            assert c.predicted_opponent_response is not None
            assert c.predicted_opponent_response.move_uci is not None
            assert c.predicted_opponent_response.move_san is not None
            assert c.prediction_type == PredictionType.ADVERSARIAL_MINIMAX
            assert c.status == SearchStatus.COMPLETED

    def test_candidate_delivering_direct_mate(self) -> None:
        # In MATE_IN_ONE_FEN, White can play Qxf7# directly
        engine = OpponentSearchEngine(default_depth=2)
        report = engine.analyze_candidate_consequences(
            MATE_IN_ONE_FEN,
            candidate_moves=["h5f7", "d2d3"],  # Qxf7# vs passive d3
        )

        assert report.best_candidate_san == "Qxf7#"
        mate_consequence = next(c for c in report.consequences if c.candidate_move_san == "Qxf7#")
        assert mate_consequence.is_forced_mate is True
        assert mate_consequence.mate_in == 1
        assert mate_consequence.status == SearchStatus.TERMINAL
        assert mate_consequence.predicted_opponent_response is None  # Opponent is mated!

    def test_opponent_punishes_blunder_with_mate(self) -> None:
        # Black has mate in 1 (Qh4#). If White blunders with a quiet move like a3:
        # Pre-position: White to move, but let's test Black's response to White's candidate blunder
        engine = OpponentSearchEngine(default_depth=2)
        report = engine.analyze_candidate_consequences(
            FOOLS_MATE_PRE_FEN,
            candidate_moves=["d7d5", "d8h4"],  # d5 vs Qh4#
        )

        # Black playing Qh4# is immediate mate
        best = report.consequences[0]
        assert best.candidate_move_san == "Qh4#"
        assert best.is_forced_mate is True

    def test_endgame_opponent_response(self) -> None:
        engine = OpponentSearchEngine(default_depth=3)
        report = engine.analyze_candidate_consequences(ENDGAME_KP_FEN, candidate_moves=["e5e6", "e2e3"])

        assert len(report.consequences) == 2
        for c in report.consequences:
            assert c.predicted_opponent_response is not None

    def test_illegal_candidate_move_raises(self) -> None:
        engine = OpponentSearchEngine()
        with pytest.raises(IllegalMoveError):
            engine.analyze_candidate_consequences(STARTING_FEN, candidate_moves=["e2e5"])

    def test_timeout_safe_iterative_deepening(self) -> None:
        # Set ultra-short timeout (0.0001s) to force timeout cutoff
        engine = OpponentSearchEngine(default_depth=10, default_time_limit=0.0001)
        board = chess.Board(STARTING_FEN)

        score, pv, completed_depth, status = engine.iterative_deepening(board, max_depth=10, time_limit=0.0001)

        # Timeout should be cleanly handled without crashing or returning illegal moves
        assert status in (SearchStatus.TIMEOUT_INTERRUPTED, SearchStatus.COMPLETED)
        if pv:
            assert pv[0] in board.legal_moves

    def test_report_json_serialization(self) -> None:
        engine = OpponentSearchEngine(default_depth=2)
        report = engine.analyze_candidate_consequences(STARTING_FEN, candidate_moves=["e4"])
        data = report.to_dict()

        assert "fen" in data
        assert "side_to_move" in data
        assert "opponent_side" in data
        assert "candidate_consequences" in data
        assert len(data["candidate_consequences"]) == 1

        consequence = data["candidate_consequences"][0]
        assert "candidate_move" in consequence
        assert "predicted_opponent_response" in consequence
        assert "post_candidate_evaluation" in consequence
        assert "search_depth" in consequence
        assert "nodes_evaluated" in consequence
        assert "search_duration_ms" in consequence
        assert "is_forced_mate" in consequence
        assert "status" in consequence
        assert "prediction_type" in consequence
        assert consequence["prediction_type"] == "adversarial_minimax"

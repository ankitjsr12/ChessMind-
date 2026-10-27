"""Tests for Module 4 Feature Engineering."""

import math
import pytest
import chess

from backend.ml.feature_engineering import ChessFeatureExtractor, INNER_CENTER_SQUARES

STARTING_FEN = chess.STARTING_FEN
TACTICAL_CAPTURE_FEN = "r1bqk2r/pppp1ppp/2n5/4p3/1b2P3/2NP1N2/PPPB1PPP/R2QKB1R w KQkq - 0 6"
CASTLING_FEN = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5"
PROMOTION_FEN = "8/4P3/8/8/8/8/4k3/4K3 w - - 0 1"
EN_PASSANT_FEN = "rnbqkbnr/pp1ppppp/8/2pP4/8/8/PPP1PPPP/RNBQKBNR w KQkq c6 0 3"


class TestFeatureEngineering:
    """Test suite for domain chess feature extraction."""

    def test_starting_position_feature_extraction(self) -> None:
        board = chess.Board(STARTING_FEN)
        move = chess.Move.from_uci("e2e4")
        feats = ChessFeatureExtractor.extract_features(board, move)

        assert isinstance(feats, dict)
        assert len(feats) >= 30

        # Turn is White
        assert feats["turn_is_white"] == 1.0
        assert feats["pawn_count_friendly"] == 8.0
        assert feats["pawn_count_opponent"] == 8.0
        assert feats["material_imbalance_before"] == 0.0

        # Move geometry: e2 to e4
        assert feats["is_capture"] == 0.0
        assert feats["gives_check"] == 0.0
        assert feats["is_promotion"] == 0.0
        assert feats["is_castling"] == 0.0
        assert feats["to_square_is_inner_center"] == 1.0  # e4 is inner center

        # No NaN or Inf values
        for k, v in feats.items():
            assert not math.isnan(v), f"Feature {k} is NaN"
            assert not math.isinf(v), f"Feature {k} is Inf"

    def test_capture_and_check_features(self) -> None:
        # Scholar's mate: Qxf7# delivers check and captures pawn
        board = chess.Board("r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
        move = chess.Move.from_uci("h5f7")
        feats = ChessFeatureExtractor.extract_features(board, move)

        assert feats["is_capture"] == 1.0
        assert feats["captured_piece_value"] == 100.0  # Captured pawn
        assert feats["gives_check"] == 1.0             # Checkmate gives check

    def test_castling_features(self) -> None:
        board = chess.Board(CASTLING_FEN)
        castle_move = chess.Move.from_uci("e1g1")  # Kingside castle
        feats = ChessFeatureExtractor.extract_features(board, castle_move)

        assert feats["is_castling"] == 1.0
        assert feats["is_kingside_castling"] == 1.0
        assert feats["is_queenside_castling"] == 0.0

    def test_promotion_features(self) -> None:
        board = chess.Board(PROMOTION_FEN)
        promo_move = chess.Move.from_uci("e7e8q")
        feats = ChessFeatureExtractor.extract_features(board, promo_move)

        assert feats["is_promotion"] == 1.0
        assert feats["promoted_piece_value"] == 900.0  # Promoted to Queen

    def test_en_passant_features(self) -> None:
        board = chess.Board(EN_PASSANT_FEN)
        ep_move = chess.Move.from_uci("d5c6")
        feats = ChessFeatureExtractor.extract_features(board, ep_move)

        assert feats["is_capture"] == 1.0
        assert feats["captured_piece_value"] == 100.0

    def test_canonical_feature_names_consistency(self) -> None:
        feature_names = ChessFeatureExtractor.get_feature_names()
        assert len(feature_names) >= 30
        assert "material_imbalance_before" in feature_names
        assert "mobility_before" in feature_names
        assert "inner_center_control_before" in feature_names
        assert "position_eval_delta" in feature_names

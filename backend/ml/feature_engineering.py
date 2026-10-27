"""Comprehensive chess feature engineering for position and candidate moves."""

from typing import Any, Dict, List, Optional
import chess

from backend.opponent_prediction.evaluation import PositionEvaluator

# Center squares: classical inner center and extended center
INNER_CENTER_SQUARES = [chess.D4, chess.D5, chess.E4, chess.E5]
EXTENDED_CENTER_SQUARES = [
    chess.C3, chess.C4, chess.C5, chess.C6,
    chess.D3, chess.D4, chess.D5, chess.D6,
    chess.E3, chess.E4, chess.E5, chess.E6,
    chess.F3, chess.F4, chess.F5, chess.F6,
]

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


class ChessFeatureExtractor:
    """Extracts domain-specific numerical features from chess positions and candidate moves."""

    @staticmethod
    def extract_features(
        board: chess.Board,
        move: chess.Move,
    ) -> Dict[str, float]:
        """Extract ~35 rich features for a candidate move in a given position.

        Features capture:
        - Side to move and turn context
        - Material balances and piece counts
        - Pre-move positional state (mobility, king safety, center control, pawn structure)
        - Move characteristics (capture, check, promotion, castling, geometry)
        - Post-move delta features (change in mobility, center control, material)
        """
        features: Dict[str, float] = {}
        active_color = board.turn
        opponent_color = not active_color

        # ---------------------------------------------------------
        # 1. Turn & Game Phase Features
        # ---------------------------------------------------------
        features["turn_is_white"] = 1.0 if active_color == chess.WHITE else 0.0
        features["fullmove_number"] = float(board.fullmove_number)

        # ---------------------------------------------------------
        # 2. Material Balance & Piece Counts (Before Move)
        # ---------------------------------------------------------
        white_p = len(board.pieces(chess.PAWN, chess.WHITE))
        black_p = len(board.pieces(chess.PAWN, chess.BLACK))
        white_n = len(board.pieces(chess.KNIGHT, chess.WHITE))
        black_n = len(board.pieces(chess.KNIGHT, chess.BLACK))
        white_b = len(board.pieces(chess.BISHOP, chess.WHITE))
        black_b = len(board.pieces(chess.BISHOP, chess.BLACK))
        white_r = len(board.pieces(chess.ROOK, chess.WHITE))
        black_r = len(board.pieces(chess.ROOK, chess.BLACK))
        white_q = len(board.pieces(chess.QUEEN, chess.WHITE))
        black_q = len(board.pieces(chess.QUEEN, chess.BLACK))

        features["pawn_count_friendly"] = float(white_p if active_color == chess.WHITE else black_p)
        features["pawn_count_opponent"] = float(black_p if active_color == chess.WHITE else white_p)
        features["knight_count_friendly"] = float(white_n if active_color == chess.WHITE else black_n)
        features["knight_count_opponent"] = float(black_n if active_color == chess.WHITE else white_n)
        features["bishop_count_friendly"] = float(white_b if active_color == chess.WHITE else black_b)
        features["bishop_count_opponent"] = float(black_b if active_color == chess.WHITE else white_b)
        features["rook_count_friendly"] = float(white_r if active_color == chess.WHITE else black_r)
        features["rook_count_opponent"] = float(black_r if active_color == chess.WHITE else white_r)
        features["queen_count_friendly"] = float(white_q if active_color == chess.WHITE else black_q)
        features["queen_count_opponent"] = float(black_q if active_color == chess.WHITE else white_q)

        friendly_mat = (
            features["pawn_count_friendly"] * 100
            + features["knight_count_friendly"] * 320
            + features["bishop_count_friendly"] * 330
            + features["rook_count_friendly"] * 500
            + features["queen_count_friendly"] * 900
        )
        opponent_mat = (
            features["pawn_count_opponent"] * 100
            + features["knight_count_opponent"] * 320
            + features["bishop_count_opponent"] * 330
            + features["rook_count_opponent"] * 500
            + features["queen_count_opponent"] * 900
        )
        material_imbalance_before = friendly_mat - opponent_mat
        features["material_imbalance_before"] = float(material_imbalance_before)

        # ---------------------------------------------------------
        # 3. Positional State Before Move (Mobility, Center, King)
        # ---------------------------------------------------------
        mobility_before = len(list(board.legal_moves))
        features["mobility_before"] = float(mobility_before)

        inner_center_ctrl_before = sum(
            len(board.attackers(active_color, sq)) for sq in INNER_CENTER_SQUARES
        )
        features["inner_center_control_before"] = float(inner_center_ctrl_before)

        # King safety: distance of king from board center
        king_sq = board.king(active_color)
        if king_sq is not None:
            king_rank = chess.square_rank(king_sq)
            king_file = chess.square_file(king_sq)
            features["king_dist_from_center"] = float(abs(king_rank - 3.5) + abs(king_file - 3.5))
        else:
            features["king_dist_from_center"] = 0.0

        # Static heuristic score before move
        pst_before = PositionEvaluator.evaluate_relative(board)
        features["position_eval_before"] = float(pst_before)

        # ---------------------------------------------------------
        # 4. Candidate Move Specific Characteristics
        # ---------------------------------------------------------
        from_sq = move.from_square
        to_sq = move.to_square
        moving_piece = board.piece_at(from_sq)
        moving_piece_type = moving_piece.piece_type if moving_piece else chess.PAWN
        features["moving_piece_type"] = float(moving_piece_type)

        from_rank, from_file = chess.square_rank(from_sq), chess.square_file(from_sq)
        to_rank, to_file = chess.square_rank(to_sq), chess.square_file(to_sq)
        features["move_distance_chebyshev"] = float(max(abs(to_rank - from_rank), abs(to_file - from_file)))
        features["move_distance_manhattan"] = float(abs(to_rank - from_rank) + abs(to_file - from_file))

        # Destination center proximity
        features["to_square_is_inner_center"] = 1.0 if to_sq in INNER_CENTER_SQUARES else 0.0
        features["to_square_is_extended_center"] = 1.0 if to_sq in EXTENDED_CENTER_SQUARES else 0.0

        # Tactical move flags
        is_capture = board.is_capture(move)
        features["is_capture"] = 1.0 if is_capture else 0.0

        captured_piece = board.piece_at(to_sq)
        if captured_piece:
            cap_val = PIECE_VALUES.get(captured_piece.piece_type, 0)
        elif board.is_en_passant(move):
            cap_val = 100
        else:
            cap_val = 0
        features["captured_piece_value"] = float(cap_val)

        # Checks and mates
        gives_check = board.gives_check(move)
        features["gives_check"] = 1.0 if gives_check else 0.0

        # Promotion
        features["is_promotion"] = 1.0 if move.promotion is not None else 0.0
        features["promoted_piece_value"] = float(PIECE_VALUES.get(move.promotion, 0) if move.promotion else 0)

        # Castling
        is_castling = board.is_castling(move)
        features["is_castling"] = 1.0 if is_castling else 0.0
        features["is_kingside_castling"] = 1.0 if board.is_kingside_castling(move) else 0.0
        features["is_queenside_castling"] = 1.0 if board.is_queenside_castling(move) else 0.0

        # Destination attack / defense balance
        dest_enemy_attackers = len(board.attackers(opponent_color, to_sq))
        dest_friendly_defenders = len(board.attackers(active_color, to_sq))
        features["destination_enemy_attackers"] = float(dest_enemy_attackers)
        features["destination_friendly_defenders"] = float(dest_friendly_defenders)
        features["destination_is_defended"] = 1.0 if dest_friendly_defenders > 0 else 0.0
        features["destination_is_attacked"] = 1.0 if dest_enemy_attackers > 0 else 0.0

        # ---------------------------------------------------------
        # 5. Position Simulation & Delta Features (After Move)
        # ---------------------------------------------------------
        board.push(move)

        # Opponent mobility after move (lower opponent mobility is better for active player)
        opponent_mobility_after = len(list(board.legal_moves))
        features["opponent_mobility_after"] = float(opponent_mobility_after)

        # Post-move inner center control
        inner_center_ctrl_after = sum(
            len(board.attackers(active_color, sq)) for sq in INNER_CENTER_SQUARES
        )
        features["center_control_delta"] = float(inner_center_ctrl_after - inner_center_ctrl_before)

        # Post-move static evaluation (negated because turn flipped)
        pst_after = -PositionEvaluator.evaluate_relative(board)
        features["position_eval_delta"] = float(pst_after - pst_before)

        board.pop()

        return features

    @classmethod
    def get_feature_names(cls) -> List[str]:
        """Return canonical ordered list of all feature names."""
        board = chess.Board()
        move = list(board.legal_moves)[0]
        feats = cls.extract_features(board, move)
        return list(feats.keys())

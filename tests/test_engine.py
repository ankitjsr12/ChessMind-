"""Comprehensive unit tests for ChessEngine, models, and exceptions."""

from typing import List, Optional
import pytest
import chess

from backend.chess_engine import (
    ChessEngine,
    BoardState,
    CastlingRights,
    GameResult,
    GameTermination,
    MoveRecord,
    MoveResult,
    PieceColor,
    PieceType,
    TerminationReason,
    ChessEngineException,
    GameOverError,
    IllegalMoveError,
    InvalidFENError,
    InvalidMoveError,
    InvalidPGNError,
    NoMovesToUndoError,
)
from backend.chess_engine.models import BaseMovePredictor


class TestBoardInitializationAndFEN:
    """Tests for board creation, FEN validation, and board resetting."""

    def test_default_initialization(self) -> None:
        engine = ChessEngine()
        assert engine.fen == ChessEngine.STARTING_FEN
        assert engine.turn == PieceColor.WHITE
        assert engine.fullmove_number == 1
        assert engine.halfmove_clock == 0
        assert not engine.is_check()
        assert not engine.is_checkmate()
        assert not engine.is_game_over()
        assert len(engine.get_move_history()) == 0

    def test_initialization_with_valid_custom_fen(self) -> None:
        custom_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        engine = ChessEngine(custom_fen)
        assert engine.fen == custom_fen
        assert engine.turn == PieceColor.WHITE
        assert engine.fullmove_number == 3
        assert engine.halfmove_clock == 2

    def test_is_valid_fen_helper(self) -> None:
        assert ChessEngine.is_valid_fen(ChessEngine.STARTING_FEN) is True
        assert ChessEngine.is_valid_fen("invalid fen string") is False
        # Board with no kings
        assert ChessEngine.is_valid_fen("8/8/8/8/8/8/8/8 w - - 0 1") is False

    def test_initialization_with_invalid_fen_syntax(self) -> None:
        with pytest.raises(InvalidFENError) as exc_info:
            ChessEngine("invalid fen string")
        assert "Invalid FEN" in str(exc_info.value)
        assert exc_info.value.fen == "invalid fen string"

    def test_initialization_with_illegal_fen_missing_kings(self) -> None:
        with pytest.raises(InvalidFENError) as exc_info:
            ChessEngine("8/8/8/8/8/8/8/8 w - - 0 1")
        assert "Missing" in str(exc_info.value)

    def test_reset_functionality(self) -> None:
        engine = ChessEngine()
        engine.make_move("e4")
        engine.make_move("e5")
        assert len(engine.get_move_history()) == 2

        engine.reset()
        assert engine.fen == ChessEngine.STARTING_FEN
        assert len(engine.get_move_history()) == 0
        assert engine.turn == PieceColor.WHITE

    def test_reset_to_fen(self) -> None:
        engine = ChessEngine()
        custom_fen = "4k3/8/8/8/8/8/8/4K2R w K - 0 1"
        engine.reset_to_fen(custom_fen)
        assert engine.fen == custom_fen
        assert len(engine.get_move_history()) == 0

        with pytest.raises(InvalidFENError):
            engine.reset_to_fen("garbage")


class TestMoveValidationAndExecution:
    """Tests for normal piece moves, move formats, and error handling."""

    def test_make_move_uci_and_san(self) -> None:
        engine = ChessEngine()

        # White plays e4 (SAN)
        res1 = engine.make_move("e4")
        assert isinstance(res1, MoveResult)
        assert res1.move_record.san == "e4"
        assert res1.move_record.uci == "e2e4"
        assert res1.move_record.turn == PieceColor.WHITE
        assert res1.move_record.piece_moved == "P"
        assert res1.move_record.captured_piece is None
        assert not res1.move_record.is_capture
        assert engine.turn == PieceColor.BLACK

        # Black plays e5 (UCI)
        res2 = engine.make_move("e7e5")
        assert res2.move_record.san == "e5"
        assert res2.move_record.uci == "e7e5"
        assert res2.move_record.turn == PieceColor.BLACK
        assert res2.move_record.piece_moved == "p"
        assert engine.turn == PieceColor.WHITE

    def test_make_move_with_chess_move_object(self) -> None:
        engine = ChessEngine()
        move_obj = chess.Move.from_uci("g1f3")
        res = engine.make_move(move_obj)
        assert res.move_record.san == "Nf3"
        assert res.move_record.uci == "g1f3"

    def test_legal_moves_queries(self) -> None:
        engine = ChessEngine()
        uci_moves = engine.get_legal_moves_uci()
        san_moves = engine.get_legal_moves_san()

        assert len(uci_moves) == 20  # 16 pawn moves + 4 knight moves
        assert len(san_moves) == 20
        assert "e2e4" in uci_moves
        assert "e4" in san_moves
        assert "g1f3" in uci_moves
        assert "Nf3" in san_moves

        with pytest.raises(ValueError):
            engine.get_legal_moves(format="unsupported")

    def test_is_legal_move(self) -> None:
        engine = ChessEngine()
        assert engine.is_legal_move("e4") is True
        assert engine.is_legal_move("e2e4") is True
        assert engine.is_legal_move("e5") is False  # Black's pawn on move 1
        assert engine.is_legal_move("e2e5") is False  # Cannot move 3 squares
        assert engine.is_legal_move("zz99") is False

    def test_invalid_move_syntax(self) -> None:
        engine = ChessEngine()
        with pytest.raises(InvalidMoveError):
            engine.make_move("zz99")
        with pytest.raises(InvalidMoveError):
            engine.make_move("e9e5")
        with pytest.raises(InvalidMoveError):
            engine.make_move("")
        with pytest.raises(InvalidMoveError):
            engine.make_move(123)  # type: ignore

    def test_illegal_move_detection(self) -> None:
        engine = ChessEngine()
        # White pawn cannot jump 3 squares
        with pytest.raises(IllegalMoveError):
            engine.make_move("e2e5")

        # White cannot move opponent's piece
        with pytest.raises(IllegalMoveError):
            engine.make_move("e7e5")

        # White bishop cannot jump over pawns
        with pytest.raises(IllegalMoveError):
            engine.make_move("f1c4")


class TestSpecialChessRules:
    """Tests for Castling, En Passant, and Pawn Promotion."""

    def test_castling_kingside_and_queenside_white(self) -> None:
        # FEN with White castling available both sides
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        engine = ChessEngine(fen)

        rights = engine.get_castling_rights()
        assert rights.white_kingside is True
        assert rights.white_queenside is True
        assert rights.black_kingside is True
        assert rights.black_queenside is True

        # White castles kingside
        res = engine.make_move("O-O")
        assert res.move_record.is_castling is True
        assert res.move_record.uci == "e1g1"
        assert res.move_record.san == "O-O"

    def test_castling_queenside_black(self) -> None:
        fen = "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1"
        engine = ChessEngine(fen)

        res = engine.make_move("O-O-O")
        assert res.move_record.is_castling is True
        assert res.move_record.uci == "e8c8"
        assert res.move_record.san == "O-O-O"

    def test_cannot_castle_through_check(self) -> None:
        # Enemy rook attacks f1 square through which White king must pass to castle kingside
        fen = "r3k2r/8/8/8/5r2/8/8/R3K2R w KQkq - 0 1"
        engine = ChessEngine(fen)
        with pytest.raises(IllegalMoveError):
            engine.make_move("O-O")

    def test_en_passant_execution(self) -> None:
        # Setup position where White can play en passant
        engine = ChessEngine()
        engine.make_move("e4")
        engine.make_move("a6")
        engine.make_move("e5")
        engine.make_move("d5")  # Black pawn double moves adjacent to White pawn

        state = engine.get_board_state()
        assert state.en_passant_square == "d6"

        # Execute en passant capture
        res = engine.make_move("exd6")
        assert res.move_record.is_en_passant is True
        assert res.move_record.is_capture is True
        assert res.move_record.captured_piece == "p"
        assert res.move_record.san == "exd6"

        # Verify captured pawn at d5 is gone
        matrix = engine.get_board_matrix()
        # d5 corresponds to file d (col 3), rank 5 (row 8-5 = 3)
        assert matrix[3][3] is None

    def test_pawn_promotion_to_queen(self) -> None:
        # White pawn on a7 ready to promote on a8
        fen = "8/P7/8/8/8/8/8/4K2k w - - 0 1"
        engine = ChessEngine(fen)

        res = engine.make_move("a8=Q")
        assert res.move_record.is_promotion is True
        assert res.move_record.promotion_piece == "Q"
        assert res.move_record.uci == "a7a8q"

        piece_counts = engine.get_piece_counts()
        assert piece_counts["Q"] == 1
        assert piece_counts["P"] == 0

    def test_pawn_promotion_underpromotion_to_knight(self) -> None:
        # White pawn promotes to Knight with UCI format
        fen = "8/P7/8/8/8/8/8/4K2k w - - 0 1"
        engine = ChessEngine(fen)

        res = engine.make_move("a7a8n")
        assert res.move_record.is_promotion is True
        assert res.move_record.promotion_piece == "N"

        piece_counts = engine.get_piece_counts()
        assert piece_counts["N"] == 1


class TestUndoFunctionality:
    """Tests for single and multiple move undos and history management."""

    def test_single_undo(self) -> None:
        engine = ChessEngine()
        start_fen = engine.fen

        engine.make_move("e4")
        assert engine.fen != start_fen
        assert len(engine.get_move_history()) == 1

        undone = engine.undo_move()
        assert undone.uci == "e2e4"
        assert engine.fen == start_fen
        assert len(engine.get_move_history()) == 0
        assert engine.turn == PieceColor.WHITE

    def test_multiple_undos(self) -> None:
        engine = ChessEngine()
        engine.make_move("e4")
        engine.make_move("e5")
        engine.make_move("Nf3")

        assert len(engine.get_move_history()) == 3
        undone_list = engine.undo_moves(2)
        assert len(undone_list) == 2
        assert undone_list[0].uci == "g1f3"
        assert undone_list[1].uci == "e7e5"
        assert len(engine.get_move_history()) == 1
        assert engine.turn == PieceColor.BLACK

    def test_undo_on_empty_history_raises(self) -> None:
        engine = ChessEngine()
        with pytest.raises(NoMovesToUndoError):
            engine.undo_move()

    def test_undo_excessive_count_raises(self) -> None:
        engine = ChessEngine()
        engine.make_move("e4")
        with pytest.raises(NoMovesToUndoError):
            engine.undo_moves(5)

    def test_undo_invalid_count_raises(self) -> None:
        engine = ChessEngine()
        with pytest.raises(ValueError):
            engine.undo_moves(0)


class TestGameTerminationAndResults:
    """Tests for Checkmate, Stalemate, Draw rules, and terminal move guards."""

    def test_scholars_mate_detection(self) -> None:
        engine = ChessEngine()
        engine.make_move("e4")
        engine.make_move("e5")
        engine.make_move("Bc4")
        engine.make_move("Nc6")
        engine.make_move("Qh5")
        engine.make_move("Nf6")
        res = engine.make_move("Qxf7#")

        assert engine.is_checkmate() is True
        assert engine.is_check() is True
        assert engine.is_game_over() is True

        term = engine.get_game_result()
        assert term.is_terminated is True
        assert term.winner == PieceColor.WHITE
        assert term.result_code == GameResult.WHITE_WINS
        assert term.reason == TerminationReason.CHECKMATE
        assert "White wins" in term.description

        # Moving after game over must raise GameOverError
        with pytest.raises(GameOverError):
            engine.make_move("a6")

    def test_stalemate_detection(self) -> None:
        # Standard corner stalemate: Black king on a8, White queen on b6, White king on a1
        stalemate_fen = "k7/8/1Q6/8/8/8/8/K7 b - - 0 1"
        engine = ChessEngine(stalemate_fen)

        assert engine.is_stalemate() is True
        assert engine.is_check() is False
        assert engine.is_draw() is True
        assert engine.is_game_over() is True

        term = engine.get_game_result()
        assert term.is_terminated is True
        assert term.winner is None
        assert term.result_code == GameResult.DRAW
        assert term.reason == TerminationReason.STALEMATE

    def test_insufficient_material_king_vs_king(self) -> None:
        fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
        engine = ChessEngine(fen)

        assert engine.is_insufficient_material() is True
        assert engine.is_draw() is True

        term = engine.get_game_result()
        assert term.result_code == GameResult.DRAW
        assert term.reason == TerminationReason.INSUFFICIENT_MATERIAL

    def test_threefold_repetition_claim(self) -> None:
        engine = ChessEngine()
        # White and Black cycle knights back and forth
        moves = ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1", "Ng8"]
        for m in moves:
            engine.make_move(m)

        assert engine.can_claim_threefold_repetition() is True
        assert engine.can_claim_draw() is True
        assert engine.is_draw() is True

        # Claim the draw
        term = engine.claim_draw()
        assert term.is_terminated is True
        assert term.result_code == GameResult.DRAW
        assert term.reason == TerminationReason.THREEFOLD_REPETITION
        assert engine.is_game_over() is True

        # Making a move after claiming draw raises GameOverError
        with pytest.raises(GameOverError):
            engine.make_move("e4")


class TestPGNImportAndExport:
    """Tests for PGN serialization and replaying."""

    def test_pgn_export_and_import_roundtrip(self) -> None:
        engine = ChessEngine()
        engine.make_move("e4")
        engine.make_move("e5")
        engine.make_move("Nf3")
        engine.make_move("Nc6")

        pgn_str = engine.export_pgn(
            headers={"Event": "World Championship", "White": "Carlsen", "Black": "Nepo"}
        )

        assert "World Championship" in pgn_str
        assert "Carlsen" in pgn_str
        assert "1. e4 e5 2. Nf3 Nc6" in pgn_str

        # Import into fresh engine
        new_engine = ChessEngine()
        new_engine.import_pgn(pgn_str)

        assert new_engine.fen == engine.fen
        assert len(new_engine.get_move_history()) == 4
        assert new_engine.get_uci_history() == ["e2e4", "e7e5", "g1f3", "b8c6"]

    def test_import_invalid_pgn_empty(self) -> None:
        engine = ChessEngine()
        with pytest.raises(InvalidPGNError):
            engine.import_pgn("")

    def test_import_invalid_pgn_illegal_move(self) -> None:
        engine = ChessEngine()
        bad_pgn = '[Event "Bad"]\n\n1. e4 e5 2. e9e9 *'
        with pytest.raises(InvalidPGNError):
            engine.import_pgn(bad_pgn)


class TestStateInspectionAndMLFeatures:
    """Tests for BoardState, bitboards, tensors, Stockfish commands, and AI predictors."""

    def test_board_state_model(self) -> None:
        engine = ChessEngine()
        state = engine.get_board_state()

        assert isinstance(state, BoardState)
        assert len(state.legal_moves_uci) == 20
        assert len(state.board_matrix) == 8
        assert len(state.board_matrix[0]) == 8
        assert state.piece_counts["P"] == 8
        assert state.piece_counts["p"] == 8
        assert state.piece_counts["K"] == 1
        assert state.captured_pieces == {"white": [], "black": []}

        state_dict = state.to_dict()
        assert isinstance(state_dict, dict)
        assert state_dict["turn"] == "white"
        assert state_dict["is_check"] is False

    def test_captured_pieces_tracking(self) -> None:
        engine = ChessEngine()
        engine.make_move("e4")
        engine.make_move("d5")
        engine.make_move("exd5")  # White captures Black pawn

        captured = engine.get_captured_pieces()
        assert "p" in captured["black"]
        assert len(captured["white"]) == 0

    def test_stockfish_position_command(self) -> None:
        engine = ChessEngine()
        assert engine.get_stockfish_position_command() == "position startpos"

        engine.make_move("e4")
        engine.make_move("c5")
        assert engine.get_stockfish_position_command() == "position startpos moves e2e4 c7c5"

        # Custom FEN position
        custom_fen = "4k3/8/8/8/8/8/8/4K2R w K - 0 1"
        engine_fen = ChessEngine(custom_fen)
        engine_fen.make_move("O-O")
        assert engine_fen.get_stockfish_position_command() == f"position fen {custom_fen} moves e1g1"

    def test_bitboard_planes(self) -> None:
        engine = ChessEngine()
        planes = engine.get_bitboard_planes()

        assert len(planes) == 12
        for symbol in ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]:
            assert symbol in planes
            assert isinstance(planes[symbol], int)
            assert planes[symbol] >= 0

        # White pawns on rank 2: bitmask 0x000000000000FF00
        assert planes["P"] == 0x000000000000FF00

    def test_tensor_representation_shape_and_values(self) -> None:
        engine = ChessEngine()
        tensor = engine.get_tensor_representation()

        # Shape must be (14, 8, 8)
        assert len(tensor) == 14
        assert len(tensor[0]) == 8
        assert len(tensor[0][0]) == 8

        # Channel 0: White pawns. In row 6 (rank 2), all 8 columns should be 1.0
        assert sum(tensor[0][6]) == 8.0

        # Channel 12: Turn indicator for White should be 1.0 everywhere
        assert tensor[12][0][0] == 1.0

        # Channel 13: Castling rights (4 rights active = 1.0)
        assert tensor[13][0][0] == 1.0

    def test_play_ai_move_with_predictor(self) -> None:
        class DeterministicFirstMoveAI:
            """Mock AI predictor selecting the first legal move."""

            def predict_move(self, fen: str, legal_moves_uci: List[str]) -> Optional[str]:
                return legal_moves_uci[0] if legal_moves_uci else None

        engine = ChessEngine()
        ai = DeterministicFirstMoveAI()

        # Check protocol compliance
        assert isinstance(ai, BaseMovePredictor)

        result = engine.play_ai_move(ai)
        assert isinstance(result, MoveResult)
        assert len(engine.get_move_history()) == 1

    def test_play_ai_move_failure_handling(self) -> None:
        class FailingAI:
            def predict_move(self, fen: str, legal_moves_uci: List[str]) -> Optional[str]:
                return None

        engine = ChessEngine()
        with pytest.raises(ValueError):
            engine.play_ai_move(FailingAI())

    def test_ascii_and_string_representation(self) -> None:
        engine = ChessEngine()
        rendered = engine.render_ascii()
        assert "p p p p p p p p" in rendered
        assert str(engine) == rendered
        assert "ChessEngine(fen=" in repr(engine)


class TestAdvancedRulesAndEdgeCases:
    """Additional edge cases covering absolute pins, illegal king moves,

    draw variants, and data model serialization.
    """

    def test_claim_draw_when_ineligible_raises(self) -> None:
        engine = ChessEngine()
        with pytest.raises(IllegalMoveError) as exc_info:
            engine.claim_draw()
        assert "Draw cannot be claimed" in str(exc_info.value)

    def test_pinned_piece_cannot_move(self) -> None:
        # White King on e1, White Knight on e2, Black Rook on e8, Black King on g8
        pinned_fen = "4r1k1/8/8/8/8/8/4N3/4K3 w - - 0 1"
        engine = ChessEngine(pinned_fen)

        assert engine.is_legal_move("e2d4") is False
        with pytest.raises(IllegalMoveError):
            engine.make_move("e2d4")

    def test_king_cannot_walk_into_check(self) -> None:
        # White King on e1, Black Rook on d8, Black King on g8
        fen = "3r2k1/8/8/8/8/8/8/4K3 w - - 0 1"
        engine = ChessEngine(fen)

        assert engine.is_legal_move("e1d1") is False
        with pytest.raises(IllegalMoveError):
            engine.make_move("e1d1")

    def test_seventyfive_moves_rule(self) -> None:
        # 150 halfmoves without pawn move or capture with sufficient material on board
        fen = "4k3/7r/8/8/8/8/R7/4K3 w - - 150 76"
        engine = ChessEngine(fen)

        assert engine.is_seventyfive_moves() is True
        term = engine.get_game_result()
        assert term.is_terminated is True
        assert term.reason == TerminationReason.SEVENTYFIVE_MOVES
        assert term.result_code == GameResult.DRAW

    def test_fivefold_repetition_rule(self) -> None:
        engine = ChessEngine()
        # 4 cycles returns to starting position 5 times (initial + 4 repetitions)
        moves = ["Nf3", "Nf6", "Ng1", "Ng8"] * 4
        for m in moves:
            engine.make_move(m)

        assert engine.is_fivefold_repetition() is True
        term = engine.get_game_result()
        assert term.is_terminated is True
        assert term.reason == TerminationReason.FIVEFOLD_REPETITION
        assert term.result_code == GameResult.DRAW

        # Making any move now raises GameOverError
        with pytest.raises(GameOverError):
            engine.make_move("Nf3")

    def test_black_en_passant(self) -> None:
        # Setup position where Black can play en passant
        engine = ChessEngine()
        engine.make_move("a4")
        engine.make_move("e5")
        engine.make_move("h4")
        engine.make_move("e4")
        engine.make_move("d4")  # White pawn moves 2 squares past Black pawn

        state = engine.get_board_state()
        assert state.en_passant_square == "d3"

        res = engine.make_move("exd3")
        assert res.move_record.is_en_passant is True
        assert res.move_record.captured_piece == "P"
        assert res.move_record.is_capture is True

    def test_promotions_to_rook_and_bishop(self) -> None:
        fen = "8/P7/8/8/8/8/8/4K2k w - - 0 1"

        # Promotion to Rook
        engine_r = ChessEngine(fen)
        res_r = engine_r.make_move("a7a8r")
        assert res_r.move_record.is_promotion is True
        assert res_r.move_record.promotion_piece == "R"
        assert engine_r.get_piece_counts()["R"] == 1

        # Promotion to Bishop
        engine_b = ChessEngine(fen)
        res_b = engine_b.make_move("a7a8b")
        assert res_b.move_record.is_promotion is True
        assert res_b.move_record.promotion_piece == "B"
        assert engine_b.get_piece_counts()["B"] == 1

    def test_serialization_to_dict(self) -> None:
        engine = ChessEngine()
        res = engine.make_move("e4")

        data = res.to_dict()
        assert isinstance(data, dict)
        assert data["move"]["uci"] == "e2e4"
        assert data["move"]["san"] == "e4"
        assert data["move"]["turn"] == "white"
        assert data["termination"]["is_terminated"] is False
        assert data["board_state"]["turn"] == "black"


"""Unit tests for Neural Board Encoder (Module 5)."""

import pytest
import chess
import torch

from backend.deep_learning.board_encoder import (
    BoardEncoder,
    BOARD_SIZE,
    TOTAL_PLANES,
)

STARTING_FEN = chess.STARTING_FEN
TACTICAL_FEN = "r1bqk2r/pppp1ppp/2n5/4p3/1b2P3/2NP1N2/PPPB1PPP/R2QKB1R w KQkq - 0 6"
CASTLING_FEN = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5"
EN_PASSANT_FEN = "rnbqkbnr/pp1ppppp/8/2pP4/8/8/PPP1PPPP/RNBQKBNR w KQkq c6 0 3"


class TestBoardEncoder:
    """Test suite for 18-channel board tensor encoding."""

    def test_tensor_dimensions_and_type(self) -> None:
        board = chess.Board(STARTING_FEN)
        tensor = BoardEncoder.encode(board)

        assert isinstance(tensor, torch.Tensor)
        assert tensor.shape == (TOTAL_PLANES, BOARD_SIZE, BOARD_SIZE)
        assert tensor.dtype == torch.float32

    def test_starting_position_pieces(self) -> None:
        board = chess.Board(STARTING_FEN)
        tensor = BoardEncoder.encode(board)

        # White pawns (Channel 0): Rank 2 (index 1) should have 8 pawns
        assert tensor[0, 1, :].sum().item() == 8.0

        # Black pawns (Channel 6): Rank 7 (index 6) should have 8 pawns
        assert tensor[6, 6, :].sum().item() == 8.0

        # White King (Channel 5): e1 is Rank 1 (idx 0), File E (idx 4)
        assert tensor[5, 0, 4].item() == 1.0

        # Black King (Channel 11): e8 is Rank 8 (idx 7), File E (idx 4)
        assert tensor[11, 7, 4].item() == 1.0

    def test_side_to_move_encoding(self) -> None:
        board_white = chess.Board(STARTING_FEN)
        tensor_w = BoardEncoder.encode(board_white)
        # Channel 12 is all 1s when White to move
        assert tensor_w[12, :, :].mean().item() == 1.0

        board_black = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
        tensor_b = BoardEncoder.encode(board_black)
        # Channel 12 is all 0s when Black to move
        assert tensor_b[12, :, :].sum().item() == 0.0

    def test_castling_rights_encoding(self) -> None:
        board = chess.Board(STARTING_FEN)
        tensor = BoardEncoder.encode(board)

        # In starting position, all 4 castling rights are available
        assert tensor[13, :, :].mean().item() == 1.0  # White K
        assert tensor[14, :, :].mean().item() == 1.0  # White Q
        assert tensor[15, :, :].mean().item() == 1.0  # Black K
        assert tensor[16, :, :].mean().item() == 1.0  # Black Q

        # Position where White has castled and lost rights
        board_no_white_castling = chess.Board("r1bqk2r/pppp1ppp/2n5/4p3/1b2P3/2NP1N2/PPPB1PPP/R2QKB1R w kq - 0 6")
        tensor_nwc = BoardEncoder.encode(board_no_white_castling)
        assert tensor_nwc[13, :, :].sum().item() == 0.0
        assert tensor_nwc[14, :, :].sum().item() == 0.0
        assert tensor_nwc[15, :, :].mean().item() == 1.0

    def test_en_passant_encoding(self) -> None:
        board = chess.Board(EN_PASSANT_FEN)
        assert board.ep_square == chess.C6
        tensor = BoardEncoder.encode(board)

        # En passant plane (Channel 17): exactly 1 square should be active (c6 = Rank 6, File C)
        assert tensor[17, :, :].sum().item() == 1.0
        assert tensor[17, 5, 2].item() == 1.0  # Rank index 5 (Rank 6), File index 2 (File C)

    def test_batch_encoding(self) -> None:
        boards = [chess.Board(STARTING_FEN), chess.Board(TACTICAL_FEN)]
        batch_tensor = BoardEncoder.encode_batch(boards)

        assert batch_tensor.shape == (2, TOTAL_PLANES, BOARD_SIZE, BOARD_SIZE)

    def test_flat_encoding(self) -> None:
        board = chess.Board(STARTING_FEN)
        flat = BoardEncoder.encode_flat(board)
        assert flat.shape == (TOTAL_PLANES * BOARD_SIZE * BOARD_SIZE,)

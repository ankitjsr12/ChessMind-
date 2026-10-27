"""Tensor board encoding for neural chess position evaluation.

DOCUMENTED TENSOR REPRESENTATION:
Channel shape: (18, 8, 8)
- Channels 0-5:   White piece occupancy [Pawn, Knight, Bishop, Rook, Queen, King]
- Channels 6-11:  Black piece occupancy [Pawn, Knight, Bishop, Rook, Queen, King]
- Channel 12:     Side to move (all 1.0 if White, all 0.0 if Black)
- Channel 13:     White Kingside Castling Right (all 1.0 if True, else 0.0)
- Channel 14:     White Queenside Castling Right (all 1.0 if True, else 0.0)
- Channel 15:     Black Kingside Castling Right (all 1.0 if True, else 0.0)
- Channel 16:     Black Queenside Castling Right (all 1.0 if True, else 0.0)
- Channel 17:     En Passant availability (1.0 on en passant square if present, else 0.0)

Rank indexing: 0 = Rank 1 (White's side), 7 = Rank 8 (Black's side).
File indexing: 0 = File A (Queenside), 7 = File H (Kingside).
"""

from typing import List, Union
import chess
import numpy as np
import torch

# Piece type mapping: 1=Pawn, 2=Knight, 3=Bishop, 4=Rook, 5=Queen, 6=King
PIECE_TYPES = [
    chess.PAWN,
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
    chess.KING,
]
TOTAL_PLANES = 18
BOARD_SIZE = 8


class BoardEncoder:
    """Encodes python-chess Board objects into canonical 18-channel 8x8 PyTorch tensors."""

    @staticmethod
    def encode(board: Union[chess.Board, str]) -> torch.Tensor:
        """Encode a single chess board or FEN string into an (18, 8, 8) float32 tensor."""
        if isinstance(board, str):
            board = chess.Board(board)

        tensor_np = np.zeros((TOTAL_PLANES, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)

        # 1. Piece placement planes (Channels 0..11)
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is not None:
                rank = chess.square_rank(sq)
                file = chess.square_file(sq)
                piece_type_idx = piece.piece_type - 1  # 0 to 5
                channel = piece_type_idx if piece.color == chess.WHITE else (6 + piece_type_idx)
                tensor_np[channel, rank, file] = 1.0

        # 2. Side to move plane (Channel 12)
        if board.turn == chess.WHITE:
            tensor_np[12, :, :] = 1.0

        # 3. Castling rights planes (Channels 13..16)
        if board.has_kingside_castling_rights(chess.WHITE):
            tensor_np[13, :, :] = 1.0
        if board.has_queenside_castling_rights(chess.WHITE):
            tensor_np[14, :, :] = 1.0
        if board.has_kingside_castling_rights(chess.BLACK):
            tensor_np[15, :, :] = 1.0
        if board.has_queenside_castling_rights(chess.BLACK):
            tensor_np[16, :, :] = 1.0

        # 4. En Passant plane (Channel 17)
        if board.ep_square is not None:
            ep_rank = chess.square_rank(board.ep_square)
            ep_file = chess.square_file(board.ep_square)
            tensor_np[17, ep_rank, ep_file] = 1.0

        return torch.from_numpy(tensor_np)

    @staticmethod
    def encode_flat(board: Union[chess.Board, str]) -> torch.Tensor:
        """Encode board into a 1D vector of shape (1152,) for MLP feed-forward networks."""
        spatial = BoardEncoder.encode(board)
        return spatial.view(-1)

    @staticmethod
    def encode_batch(boards: List[Union[chess.Board, str]]) -> torch.Tensor:
        """Encode a batch of boards into an (N, 18, 8, 8) batch tensor."""
        tensors = [BoardEncoder.encode(b) for b in boards]
        return torch.stack(tensors, dim=0)

    @classmethod
    def get_plane_descriptions(cls) -> List[str]:
        """Return descriptions for each of the 18 representation planes."""
        return [
            "White Pawns",
            "White Knights",
            "White Bishops",
            "White Rooks",
            "White Queens",
            "White Kings",
            "Black Pawns",
            "Black Knights",
            "Black Bishops",
            "Black Rooks",
            "Black Queens",
            "Black Kings",
            "Side to Move (1.0 = White, 0.0 = Black)",
            "White Kingside Castling Right",
            "White Queenside Castling Right",
            "Black Kingside Castling Right",
            "Black Queenside Castling Right",
            "En Passant Target Square",
        ]

"""Inference service for Neural Chess Position Evaluation and candidate move ranking."""

import os
import time
from typing import Any, Dict, List, Optional, Union
import chess
import torch
import torch.nn as nn

from backend.chess_engine import ChessEngine, IllegalMoveError, InvalidFENError
from backend.deep_learning.board_encoder import BoardEncoder
from backend.deep_learning.model import create_neural_model, target_to_cp
from backend.deep_learning.train import get_optimal_device


class NeuralModelNotTrainedError(FileNotFoundError):
    """Raised when an inference call is made before neural weights are trained or found."""

    def __init__(self, checkpoint_path: str) -> None:
        msg = (
            f"No trained neural model found at '{checkpoint_path}'. "
            "Please train the model first using 'python -m backend.deep_learning.train' "
            "or by calling 'backend.deep_learning.train_neural_evaluator()'."
        )
        super().__init__(msg)
        self.checkpoint_path = checkpoint_path


class NeuralPositionEvaluator:
    """Evaluates chess positions and ranks candidate moves using a trained PyTorch model."""

    DEFAULT_CHECKPOINT_PATH = os.path.join("models", "neural", "best_evaluator.pt")

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        device: Optional[torch.device] = None,
        autoload: bool = True,
    ) -> None:
        self.checkpoint_path = checkpoint_path or self.DEFAULT_CHECKPOINT_PATH
        self.device = device or get_optimal_device()
        self.model: Optional[nn.Module] = None
        self.model_type: str = "cnn"
        self.target_scale: float = 400.0
        self.best_val_loss: float = 0.0

        if autoload and os.path.exists(self.checkpoint_path):
            self.load_model(self.checkpoint_path)

    @property
    def is_trained(self) -> bool:
        """Verify whether model is instantiated and loaded into memory."""
        return self.model is not None

    def load_model(self, checkpoint_path: str) -> None:
        """Load trained neural network checkpoint and weights."""
        if not os.path.exists(checkpoint_path):
            raise NeuralModelNotTrainedError(checkpoint_path)

        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model_type = checkpoint.get("model_type", "cnn")
        in_channels = checkpoint.get("in_channels", 18)
        self.target_scale = checkpoint.get("target_scale", 400.0)
        self.best_val_loss = checkpoint.get("best_val_loss", 0.0)

        model = create_neural_model(model_type=self.model_type, in_channels=in_channels)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(self.device)
        model.eval()

        self.model = model
        self.checkpoint_path = checkpoint_path

    def evaluate_position(
        self,
        board_or_fen: Union[chess.Board, str, ChessEngine],
    ) -> Dict[str, Any]:
        """Evaluate a position and return white/relative centipawns and win probabilities.

        Returns:
            Dict containing eval_white_cp, eval_relative_cp, win_probability, display_text.
        """
        if not self.is_trained:
            if os.path.exists(self.checkpoint_path):
                self.load_model(self.checkpoint_path)
            else:
                raise NeuralModelNotTrainedError(self.checkpoint_path)

        if isinstance(board_or_fen, ChessEngine):
            board = board_or_fen.board
        elif isinstance(board_or_fen, str):
            try:
                board = chess.Board(board_or_fen)
            except Exception as e:
                raise InvalidFENError(board_or_fen, reason=str(e)) from e
        else:
            board = board_or_fen

        # 1. Encode position
        tensor = BoardEncoder.encode(board).unsqueeze(0).to(self.device)

        # 2. Forward pass
        with torch.no_grad():
            pred_target = self.model(tensor).item()

        white_cp = target_to_cp(pred_target, scale=self.target_scale)
        relative_cp = white_cp if board.turn == chess.WHITE else -white_cp
        win_prob = (pred_target + 1.0) / 2.0  # Normalized to [0.0, 1.0]

        disp_sign = "+" if white_cp > 0 else ""
        display_text = f"{disp_sign}{white_cp / 100.0:.2f}"

        return {
            "fen": board.fen(),
            "turn": "white" if board.turn == chess.WHITE else "black",
            "eval_white_cp": round(white_cp, 1),
            "eval_relative_cp": round(relative_cp, 1),
            "white_win_probability": round(win_prob, 4),
            "display_text": display_text,
            "model_type": self.model_type,
            "source": "neural_network",
        }

    def evaluate_candidate_moves(
        self,
        board_or_fen: Union[chess.Board, str, ChessEngine],
        candidate_moves: Optional[List[Union[str, chess.Move]]] = None,
    ) -> List[Dict[str, Any]]:
        """Simulate candidate moves and rank them by neural evaluation of the resulting board state."""
        if not self.is_trained:
            if os.path.exists(self.checkpoint_path):
                self.load_model(self.checkpoint_path)
            else:
                raise NeuralModelNotTrainedError(self.checkpoint_path)

        if isinstance(board_or_fen, ChessEngine):
            engine = board_or_fen
        elif isinstance(board_or_fen, str):
            try:
                engine = ChessEngine(board_or_fen)
            except Exception as e:
                raise InvalidFENError(board_or_fen, reason=str(e)) from e
        else:
            engine = ChessEngine(board_or_fen.fen())

        board = engine.board
        active_color = board.turn

        # Determine moves to evaluate
        if candidate_moves is None or len(candidate_moves) == 0:
            moves_to_check = list(board.legal_moves)
        else:
            moves_to_check = []
            for m in candidate_moves:
                parsed_move = engine.parse_move(m)
                if parsed_move not in board.legal_moves:
                    raise IllegalMoveError(
                        move_str=str(m),
                        fen=engine.fen,
                        reason="Candidate move is illegal in starting position",
                    )
                moves_to_check.append(parsed_move)

        if not moves_to_check:
            return []

        # Simulate moves and encode post-move positions in batch
        post_boards: List[chess.Board] = []
        move_metadata: List[Tuple[chess.Move, str, bool, bool]] = []

        for m in moves_to_check:
            san = board.san(m)
            is_cap = board.is_capture(m)
            is_chk = board.gives_check(m)
            move_metadata.append((m, san, is_cap, is_chk))

            board.push(m)
            post_boards.append(board.copy())
            board.pop()

        # Batch forward pass for optimal performance
        batch_tensors = BoardEncoder.encode_batch(post_boards).to(self.device)
        with torch.no_grad():
            batch_targets = self.model(batch_tensors).cpu().numpy().tolist()

        results: List[Dict[str, Any]] = []
        for (move, san, is_cap, is_chk), target in zip(move_metadata, batch_targets):
            white_cp = target_to_cp(target, scale=self.target_scale)
            # From perspective of the player making the candidate move:
            player_cp = white_cp if active_color == chess.WHITE else -white_cp

            results.append({
                "move_uci": move.uci(),
                "move_san": san,
                "is_capture": is_cap,
                "is_check": is_chk,
                "post_move_eval_white_cp": round(white_cp, 1),
                "post_move_eval_player_cp": round(player_cp, 1),
                "display_text": f"{'+' if player_cp > 0 else ''}{player_cp / 100.0:.2f}",
                "player_win_prob": round((target + 1.0) / 2.0 if active_color == chess.WHITE else (1.0 - target) / 2.0, 4),
            })

        # Rank moves descending: highest post-move score for player first
        results.sort(key=lambda x: x["post_move_eval_player_cp"], reverse=True)
        for rank_idx, item in enumerate(results, start=1):
            item["rank"] = rank_idx

        return results

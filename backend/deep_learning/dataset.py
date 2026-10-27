"""PyTorch Dataset and data pipeline for chess position evaluation.

DATA PIPELINE BEST PRACTICES:
1. Reuses licensed CC0 public domain master PGN datasets.
2. Group split by `game_id` across Train, Validation, and Test sets to prevent data leakage.
3. Generates continuous target labels: y = tanh(eval_cp / 400.0) in [-1.0, 1.0].
4. Categorizes game phase (opening: plies 0-20, middlegame: plies 21-50, endgame: plies > 50).
"""

from typing import Dict, List, Optional, Tuple, Union
import chess
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
import torch
from torch.utils.data import Dataset

from backend.deep_learning.board_encoder import BoardEncoder
from backend.deep_learning.model import cp_to_target
from backend.ml.data_loader import ChessDataLoader
from backend.opponent_prediction.evaluation import PositionEvaluator


class ChessPositionDataset(Dataset):
    """PyTorch Dataset yielding 18-channel board tensors and scalar target evaluations."""

    def __init__(
        self,
        records: List[Dict[str, Union[str, float, int]]],
        preload_tensors: bool = True,
    ) -> None:
        self.records = records
        self.preload_tensors = preload_tensors

        if preload_tensors:
            tensors = []
            targets = []
            for r in records:
                t = BoardEncoder.encode(str(r["fen"]))
                tensors.append(t)
                targets.append(float(r["target"]))
            self.tensors = torch.stack(tensors, dim=0)
            self.targets = torch.tensor(targets, dtype=torch.float32)
        else:
            self.tensors = None
            self.targets = torch.tensor([float(r["target"]) for r in records], dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.preload_tensors and self.tensors is not None:
            return self.tensors[idx], self.targets[idx]

        r = self.records[idx]
        tensor = BoardEncoder.encode(str(r["fen"]))
        target = self.targets[idx]
        return tensor, target


class DeepLearningDataPipeline:
    """Prepares, labels, and splits chess game positions into Train, Val, and Test datasets."""

    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed
        self.loader = ChessDataLoader(random_seed=random_seed)

    def build_position_records(
        self,
        max_games: int = 50,
        max_positions_per_game: int = 15,
        pgn_file_path: Optional[str] = None,
    ) -> List[Dict[str, Union[str, float, int]]]:
        """Extract labeled positions from PGN games with game phase tracking."""
        if pgn_file_path:
            df_raw = self.loader.load_from_pgn_file(pgn_file_path, max_games=max_games)
        else:
            df_raw = self.loader.load_sample_dataset(max_games=max_games)

        # Retain unique positions (positive played moves represent authentic board states)
        df_positions = df_raw.drop_duplicates(subset=["game_id", "ply"]).copy()

        records: List[Dict[str, Union[str, float, int]]] = []
        for _, row in df_positions.iterrows():
            fen = str(row["fen"])
            game_id = str(row["game_id"])
            ply = int(row["ply"])
            board = chess.Board(fen)

            # Generate reference evaluation from White's perspective
            white_cp = PositionEvaluator.evaluate(board)
            target = cp_to_target(white_cp)

            # Determine game phase
            if ply <= 20:
                phase = "opening"
            elif ply <= 50:
                phase = "middlegame"
            else:
                phase = "endgame"

            records.append(
                {
                    "game_id": game_id,
                    "ply": ply,
                    "fen": fen,
                    "eval_cp": float(white_cp),
                    "target": target,
                    "phase": phase,
                }
            )

        return records

    def split_datasets(
        self,
        records: List[Dict[str, Union[str, float, int]]],
        val_size: float = 0.15,
        test_size: float = 0.15,
    ) -> Tuple[ChessPositionDataset, ChessPositionDataset, ChessPositionDataset, List[Dict[str, Any]]]:
        """Perform 3-way leakage-free group split by `game_id` into Train, Val, and Test sets."""
        df = pd.DataFrame(records)
        groups = df["game_id"].values

        # 1. Split off test set
        gss_test = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=self.random_seed)
        train_val_idx, test_idx = next(gss_test.split(df, groups=groups))

        df_train_val = df.iloc[train_val_idx].reset_index(drop=True)
        df_test = df.iloc[test_idx].reset_index(drop=True)

        # 2. Split train_val into train and validation
        rel_val_size = val_size / (1.0 - test_size)
        gss_val = GroupShuffleSplit(n_splits=1, test_size=rel_val_size, random_state=self.random_seed)
        groups_tv = df_train_val["game_id"].values
        train_idx, val_idx = next(gss_val.split(df_train_val, groups=groups_tv))

        df_train = df_train_val.iloc[train_idx].reset_index(drop=True)
        df_val = df_train_val.iloc[val_idx].reset_index(drop=True)

        # Convert to dict records
        train_records = df_train.to_dict(orient="records")
        val_records = df_val.to_dict(orient="records")
        test_records = df_test.to_dict(orient="records")

        # Datasets
        train_ds = ChessPositionDataset(train_records, preload_tensors=True)
        val_ds = ChessPositionDataset(val_records, preload_tensors=True)
        test_ds = ChessPositionDataset(test_records, preload_tensors=True)

        return train_ds, val_ds, test_ds, test_records

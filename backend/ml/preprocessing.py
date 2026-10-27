"""Preprocessing pipeline with group-based train/test splitting and feature scaling.

CRITICAL ML BEST PRACTICES ENFORCED:
1. Strict Featurization Ordering: Split data into training and test sets BEFORE fitting transformers.
2. Leakage Prevention: Group split by `game_id` so all positions from a game remain strictly
   within either train or test.
3. Feature Normalization: Fit `StandardScaler` on training data ONLY, then transform test and production inputs.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import chess
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from backend.ml.feature_engineering import ChessFeatureExtractor


@dataclass
class PreprocessedDataset:
    """Preprocessed tabular datasets with aligned feature matrices and targets."""
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: List[str]
    scaler: StandardScaler
    train_games: List[str]
    test_games: List[str]
    train_df: pd.DataFrame
    test_df: pd.DataFrame


class MLPreprocessor:
    """Handles feature matrix assembly, leakage-safe group splitting, and feature scaling."""

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.feature_extractor = ChessFeatureExtractor()

    def build_feature_dataframe(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Extract domain features for every row (position + move) in the raw dataframe."""
        feature_rows: List[Dict[str, float]] = []

        for _, row in df_raw.iterrows():
            fen = str(row["fen"])
            move_uci = str(row["move_uci"])
            board = chess.Board(fen)
            move = chess.Move.from_uci(move_uci)

            feats = self.feature_extractor.extract_features(board, move)
            feature_rows.append(feats)

        df_features = pd.DataFrame(feature_rows)

        # Merge with identification and target columns
        df_combined = pd.concat([df_raw.reset_index(drop=True), df_features], axis=1)
        return df_combined

    def prepare_train_test_split(
        self,
        df_featured: pd.DataFrame,
        test_size: float = 0.20,
        target_column: str = "is_quality_move",
    ) -> PreprocessedDataset:
        """Perform leakage-free group-based train/test split by game_id and fit StandardScaler on train."""
        feature_names = self.feature_extractor.get_feature_names()

        # Ensure no nulls or missing values
        df_cleaned = df_featured.dropna(subset=[target_column] + feature_names).copy()

        # Group split by game_id to guarantee zero game leakage between train and test
        groups = df_cleaned["game_id"].values
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=self.random_state)
        train_idx, test_idx = next(splitter.split(df_cleaned, groups=groups))

        train_df = df_cleaned.iloc[train_idx].copy()
        test_df = df_cleaned.iloc[test_idx].copy()

        train_games = train_df["game_id"].unique().tolist()
        test_games = test_df["game_id"].unique().tolist()

        # Extract feature matrices and labels
        X_train_raw = train_df[feature_names].values.astype(np.float32)
        X_test_raw = test_df[feature_names].values.astype(np.float32)
        y_train = train_df[target_column].values.astype(np.int32)
        y_test = test_df[target_column].values.astype(np.int32)

        # Fit scaler ONLY on train data
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_raw)
        X_test_scaled = scaler.transform(X_test_raw)

        return PreprocessedDataset(
            X_train=X_train_scaled,
            X_test=X_test_scaled,
            y_train=y_train,
            y_test=y_test,
            feature_names=feature_names,
            scaler=scaler,
            train_games=train_games,
            test_games=test_games,
            train_df=train_df,
            test_df=test_df,
        )

    @staticmethod
    def transform_single_position(
        board: chess.Board,
        moves: List[chess.Move],
        feature_names: List[str],
        scaler: StandardScaler,
    ) -> np.ndarray:
        """Extract and scale features for multiple candidate moves in a single board position."""
        rows: List[List[float]] = []
        for m in moves:
            feats = ChessFeatureExtractor.extract_features(board, m)
            # Ensure exact ordering according to feature_names
            ordered_vec = [feats[name] for name in feature_names]
            rows.append(ordered_vec)

        X_raw = np.array(rows, dtype=np.float32)
        X_scaled = scaler.transform(X_raw)
        return X_scaled

"""Training pipeline for candidate chess move quality prediction models."""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from typing import Dict, List, Optional, Tuple
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from backend.ml.data_loader import ChessDataLoader
from backend.ml.evaluate import ModelEvaluator
from backend.ml.preprocessing import MLPreprocessor, PreprocessedDataset
from backend.ml.schemas import ModelEvaluationMetrics, TrainingConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def train_pipeline(
    config: Optional[TrainingConfig] = None,
    pgn_file_path: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[ModelEvaluationMetrics]]:
    """Execute the end-to-end reproducible training pipeline.

    Steps:
    1. Load and parse PGN game data.
    2. Extract ~35 positional and candidate move features.
    3. Perform leakage-free group-based train/test split on `game_id`.
    4. Fit StandardScaler strictly on training set.
    5. Train Logistic Regression baseline, Random Forest, and XGBoost.
    6. Evaluate all models on held-out test data (Classification + Candidate Ranking).
    7. Select the best model and persist bundle to `models/` directory.
    8. Write evaluation reports to `artifacts/` directory.
    """
    if config is None:
        config = TrainingConfig()

    logger.info("Initializing ChessMind AI ML Training Pipeline (Seed: %d)", config.random_seed)

    # 1. Load Data
    data_loader = ChessDataLoader(
        max_positions_per_game=config.max_positions_per_game,
        candidate_alternatives_per_pos=config.candidate_alternatives_per_pos,
        random_seed=config.random_seed,
    )

    if pgn_file_path and os.path.exists(pgn_file_path):
        logger.info("Loading games from external PGN: %s", pgn_file_path)
        df_raw = data_loader.load_from_pgn_file(pgn_file_path, max_games=config.max_games)
    else:
        logger.info("Loading bundled CC0 public domain master games (Max Games: %d)", config.max_games)
        df_raw = data_loader.load_sample_dataset(max_games=config.max_games)

    logger.info("Extracted %d candidate move examples from raw games", len(df_raw))

    # 2. Extract Features
    logger.info("Extracting domain chess features (material, center, king safety, mobility, deltas)...")
    preprocessor = MLPreprocessor(random_state=config.random_seed)
    df_featured = preprocessor.build_feature_dataframe(df_raw)

    # 3. Train/Test Group Split & Scaling
    logger.info("Performing leakage-free GroupShuffleSplit on 'game_id' (Test Size: %.2f)...", config.test_size)
    preprocessed = preprocessor.prepare_train_test_split(
        df_featured,
        test_size=config.test_size,
        target_column="is_quality_move",
    )

    logger.info(
        "Train set: %d samples across %d games | Test set: %d samples across %d games",
        len(preprocessed.y_train),
        len(preprocessed.train_games),
        len(preprocessed.y_test),
        len(preprocessed.test_games),
    )

    # 4. Train Models
    models_to_evaluate: Dict[str, Any] = {}

    if "logistic_regression" in config.models_to_train:
        logger.info("Training Baseline Model: Logistic Regression...")
        lr = LogisticRegression(
            max_iter=1000,
            random_state=config.random_seed,
            class_weight="balanced",
        )
        lr.fit(preprocessed.X_train, preprocessed.y_train)
        models_to_evaluate["Logistic Regression (Baseline)"] = lr

    if "random_forest" in config.models_to_train:
        logger.info("Training Non-linear Ensemble: Random Forest...")
        rf = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=4,
            random_state=config.random_seed,
            n_jobs=-1,
        )
        rf.fit(preprocessed.X_train, preprocessed.y_train)
        models_to_evaluate["Random Forest"] = rf

    if "xgboost" in config.models_to_train:
        logger.info("Training Gradient Boosted Trees: XGBoost...")
        xgb = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=config.random_seed,
            eval_metric="logloss",
        )
        xgb.fit(preprocessed.X_train, preprocessed.y_train)
        models_to_evaluate["XGBoost"] = xgb

    # 5. Evaluate Models
    metrics_list: List[ModelEvaluationMetrics] = []
    best_model_name: Optional[str] = None
    best_model_obj: Any = None
    best_f1 = -1.0

    for name, model_obj in models_to_evaluate.items():
        metrics = ModelEvaluator.evaluate_model(
            model_name=name,
            model=model_obj,
            X_test=preprocessed.X_test,
            y_test=preprocessed.y_test,
            test_df=preprocessed.test_df,
        )
        metrics_list.append(metrics)
        logger.info(
            "[%s] Acc: %.4f | F1: %.4f | ROC-AUC: %s | Top-1 Rank Acc: %.4f | MRR: %.4f",
            name,
            metrics.accuracy,
            metrics.f1_score,
            f"{metrics.roc_auc:.4f}" if metrics.roc_auc else "N/A",
            metrics.top1_move_accuracy,
            metrics.mrr,
        )

        # Select model prioritizing F1-score & Top-1 move ranking
        if metrics.f1_score > best_f1:
            best_f1 = metrics.f1_score
            best_model_name = name
            best_model_obj = model_obj

    logger.info("Best Model Selected: %s (F1: %.4f)", best_model_name, best_f1)

    # 6. Persist Best Model Bundle
    os.makedirs(config.model_output_dir, exist_ok=True)
    model_filepath = os.path.join(config.model_output_dir, config.model_filename)

    best_metrics = next(m for m in metrics_list if m.model_name == best_model_name)
    model_bundle = {
        "model": best_model_obj,
        "scaler": preprocessed.scaler,
        "feature_names": preprocessed.feature_names,
        "model_name": best_model_name,
        "model_version": "1.0.0",
        "training_config": config.to_dict(),
        "test_metrics": best_metrics.to_dict(),
        "all_metrics": [m.to_dict() for m in metrics_list],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    joblib.dump(model_bundle, model_filepath)
    logger.info("Saved trained model bundle to: %s", model_filepath)

    # 7. Write Evaluation Artifacts
    os.makedirs(config.artifacts_output_dir, exist_ok=True)
    report_json_path = os.path.join(config.artifacts_output_dir, "training_report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "training_config": config.to_dict(),
                "best_model": best_model_name,
                "metrics": [m.to_dict() for m in metrics_list],
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )

    report_md_path = os.path.join(config.artifacts_output_dir, "evaluation_report.md")
    md_content = ModelEvaluator.generate_markdown_report(metrics_list, config.to_dict())
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("Saved evaluation reports to %s and %s", report_json_path, report_md_path)

    return model_bundle, metrics_list


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ChessMind AI Move Quality Prediction Models")
    parser.add_argument("--max-games", type=int, default=100, help="Maximum number of games to parse")
    parser.add_argument("--test-size", type=float, default=0.20, help="Test set fraction for group split")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--pgn", type=str, default=None, help="Path to external PGN file (optional)")
    parser.add_argument("--model-dir", type=str, default="models", help="Directory to save model checkpoint")
    parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Directory to save evaluation reports")

    args = parser.parse_args()

    config = TrainingConfig(
        max_games=args.max_games,
        test_size=args.test_size,
        random_seed=args.seed,
        model_output_dir=args.model_dir,
        artifacts_output_dir=args.artifacts_dir,
    )

    train_pipeline(config=config, pgn_file_path=args.pgn)


if __name__ == "__main__":
    main()

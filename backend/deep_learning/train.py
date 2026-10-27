"""Training pipeline for Neural Chess Position Evaluators.

Supports:
- Minibatch training with PyTorch DataLoader.
- Tracking training and validation loss per epoch.
- Automatic hardware acceleration (Apple Silicon MPS / NVIDIA CUDA / CPU fallback).
- Early stopping with patience.
- Checkpoint persistence with architecture metadata.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from typing import Dict, List, Optional, Tuple
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from backend.deep_learning.dataset import DeepLearningDataPipeline
from backend.deep_learning.model import create_neural_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_optimal_device() -> torch.device:
    """Detect and select best available compute accelerator (MPS, CUDA, or CPU)."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def train_neural_evaluator(
    model_type: str = "cnn",
    epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    patience: int = 3,
    max_games: int = 50,
    model_output_path: str = "models/neural/best_evaluator.pt",
    random_seed: int = 42,
    pgn_path: Optional[str] = None,
) -> Tuple[nn.Module, Dict[str, Any]]:
    """Train neural chess position evaluator with validation tracking and checkpointing."""
    torch.manual_seed(random_seed)
    device = get_optimal_device()
    logger.info("Starting Neural Network Training on device: %s (Model: %s)", device, model_type.upper())

    # 1. Prepare Data
    pipeline = DeepLearningDataPipeline(random_seed=random_seed)
    records = pipeline.build_position_records(max_games=max_games, pgn_file_path=pgn_path)
    train_ds, val_ds, test_ds, test_records = pipeline.split_datasets(records)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    logger.info(
        "Prepared dataset: %d Train positions, %d Val positions, %d Test positions",
        len(train_ds),
        len(val_ds),
        len(test_ds),
    )

    # 2. Instantiate Model, Loss & Optimizer
    model = create_neural_model(model_type=model_type, in_channels=18).to(device)
    criterion = nn.SmoothL1Loss()  # Huber loss for smooth, robust regression
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=1)

    best_val_loss = float("inf")
    best_epoch = 0
    epochs_no_improve = 0
    history: List[Dict[str, float]] = []

    # 3. Training Loop
    for epoch in range(1, epochs + 1):
        model.train()
        running_train_loss = 0.0

        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)

            optimizer.zero_grad()
            preds = model(batch_x)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()

            running_train_loss += loss.item() * batch_x.size(0)

        epoch_train_loss = running_train_loss / len(train_ds)

        # Validation
        model.eval()
        running_val_loss = 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                preds = model(batch_x)
                loss = criterion(preds, batch_y)
                running_val_loss += loss.item() * batch_x.size(0)

        epoch_val_loss = running_val_loss / max(1, len(val_ds))
        scheduler.step(epoch_val_loss)

        history.append({
            "epoch": epoch,
            "train_loss": round(epoch_train_loss, 5),
            "val_loss": round(epoch_val_loss, 5),
        })

        logger.info(
            "Epoch %d/%d — Train Loss: %.5f | Val Loss: %.5f",
            epoch,
            epochs,
            epoch_train_loss,
            epoch_val_loss,
        )

        # Early Stopping Check
        if epoch_val_loss < best_val_loss:
            best_val_loss = epoch_val_loss
            best_epoch = epoch
            epochs_no_improve = 0

            # Save best checkpoint
            os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
            checkpoint = {
                "model_state_dict": model.state_dict(),
                "model_type": model_type,
                "in_channels": 18,
                "target_scale": 400.0,
                "best_val_loss": best_val_loss,
                "best_epoch": best_epoch,
                "device": str(device),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            torch.save(checkpoint, model_output_path)
            logger.info("Saved improved checkpoint to %s (Val Loss: %.5f)", model_output_path, best_val_loss)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                logger.info("Early stopping triggered at epoch %d (No improvement for %d epochs)", epoch, patience)
                break

    training_summary = {
        "model_type": model_type,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "history": history,
        "model_output_path": model_output_path,
        "device": str(device),
        "test_records": test_records,
    }

    return model, training_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Neural Chess Position Evaluator")
    parser.add_argument("--model-type", type=str, default="cnn", choices=["cnn", "mlp"])
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--max-games", type=int, default=50)
    parser.add_argument("--output", type=str, default="models/neural/best_evaluator.pt")
    args = parser.parse_args()

    train_neural_evaluator(
        model_type=args.model_type,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_games=args.max_games,
        model_output_path=args.output,
    )


if __name__ == "__main__":
    main()

"""Neural Network Architectures for Chess Position Evaluation.

Implements:
1. Baseline Feed-Forward Network (ChessMLPEvaluator): Multilayer Perceptron over flattened board representation.
2. Convolutional Residual Network (ChessCNNEvaluator): 2D CNN with residual blocks capturing spatial chess geometries.
Target: Scalar evaluation in [-1.0, 1.0] representing normalized White winning prospect:
        y = tanh(centipawns / 400.0)
"""

from typing import Tuple
import torch
import torch.nn as nn


def cp_to_target(cp: float, scale: float = 400.0) -> float:
    """Map centipawn evaluation into bounded continuous target in [-1.0, 1.0]."""
    return float(torch.tanh(torch.tensor(cp / scale)).item())


def target_to_cp(val: float, scale: float = 400.0) -> float:
    """Convert bounded neural network output [-1.0, 1.0] back to centipawns."""
    clamped = max(-0.9999, min(0.9999, float(val)))
    return float(torch.atanh(torch.tensor(clamped)).item() * scale)


class ChessMLPEvaluator(nn.Module):
    """Baseline Feed-Forward Neural Network for position evaluation.

    Input shape: (Batch, 1152) or (Batch, 18, 8, 8) flattened.
    Output: Scalar in [-1.0, 1.0].
    """

    def __init__(self, input_dim: int = 18 * 8 * 8, hidden_dim: int = 256) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() > 2:
            x = x.view(x.size(0), -1)
        return self.network(x).squeeze(-1)


class ResidualBlock(nn.Module):
    """Basic residual block with batch normalization and skip connection."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

        if in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False),
                nn.BatchNorm2d(out_channels),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.shortcut(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return self.relu(out)


class ChessCNNEvaluator(nn.Module):
    """Convolutional Neural Network with residual connections over 18x8x8 board representation.

    Input shape: (Batch, 18, 8, 8).
    Output: Scalar in [-1.0, 1.0].
    """

    def __init__(
        self,
        in_channels: int = 18,
        conv_channels: int = 64,
        res_blocks: int = 2,
    ) -> None:
        super().__init__()
        # Initial spatial feature extraction
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, conv_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(conv_channels),
            nn.ReLU(inplace=True),
        )

        # Residual representation layers
        layers = []
        for _ in range(res_blocks):
            layers.append(ResidualBlock(conv_channels, conv_channels))
        self.res_layers = nn.Sequential(*layers)

        # Value Head
        self.value_head = nn.Sequential(
            nn.Conv2d(conv_channels, 16, kernel_size=1, bias=False),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(16 * 8 * 8, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 2:
            x = x.view(x.size(0), 18, 8, 8)
        feats = self.stem(x)
        feats = self.res_layers(feats)
        val = self.value_head(feats)
        return val.squeeze(-1)


def create_neural_model(
    model_type: str = "cnn",
    in_channels: int = 18,
) -> nn.Module:
    """Factory creating chosen neural network architecture."""
    model_type = model_type.lower()
    if model_type == "mlp":
        return ChessMLPEvaluator(input_dim=in_channels * 8 * 8)
    elif model_type in ("cnn", "convnet", "resnet"):
        return ChessCNNEvaluator(in_channels=in_channels)
    else:
        raise ValueError(f"Unknown neural model type: '{model_type}'. Choose 'mlp' or 'cnn'.")

"""Comprehensive evaluation for Neural Chess Position Evaluators."""

import math
from typing import Any, Dict, List, Optional, Tuple
import chess
import numpy as np
import torch
import torch.nn as nn

from backend.deep_learning.board_encoder import BoardEncoder
from backend.deep_learning.model import target_to_cp
from backend.deep_learning.train import get_optimal_device
from backend.opponent_prediction.evaluation import PositionEvaluator


class NeuralEvaluatorBenchmark:
    """Evaluates neural position models against material baselines and reference evaluations."""

    @staticmethod
    def evaluate_test_set(
        model: nn.Module,
        test_records: List[Dict[str, Any]],
        device: Optional[torch.device] = None,
    ) -> Dict[str, Any]:
        """Compute MAE, RMSE, Pearson correlation, and game-phase breakdown on held-out test data."""
        if device is None:
            device = get_optimal_device()

        model.eval()
        model.to(device)

        nn_errors_cp: List[float] = []
        material_errors_cp: List[float] = []

        phase_data: Dict[str, Dict[str, List[float]]] = {
            "opening": {"nn": [], "material": []},
            "middlegame": {"nn": [], "material": []},
            "endgame": {"nn": [], "material": []},
        }

        sign_matches_nn = 0
        sign_matches_mat = 0
        total_non_zero = 0

        actual_cps: List[float] = []
        pred_cps: List[float] = []

        with torch.no_grad():
            for r in test_records:
                fen = r["fen"]
                actual_cp = float(r["eval_cp"])
                phase = r.get("phase", "middlegame")
                board = chess.Board(fen)

                # 1. Neural Prediction
                tensor = BoardEncoder.encode(board).unsqueeze(0).to(device)
                pred_target = model(tensor).item()
                pred_cp = target_to_cp(pred_target)

                # 2. Material Baseline Prediction (pure piece counts)
                mat_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
                w_mat = sum(len(board.pieces(pt, chess.WHITE)) * val for pt, val in mat_vals.items())
                b_mat = sum(len(board.pieces(pt, chess.BLACK)) * val for pt, val in mat_vals.items())
                mat_cp = float(w_mat - b_mat)

                err_nn = abs(pred_cp - actual_cp)
                err_mat = abs(mat_cp - actual_cp)

                nn_errors_cp.append(err_nn)
                material_errors_cp.append(err_mat)

                if phase in phase_data:
                    phase_data[phase]["nn"].append(err_nn)
                    phase_data[phase]["material"].append(err_mat)

                actual_cps.append(actual_cp)
                pred_cps.append(pred_cp)

                if abs(actual_cp) > 20:
                    total_non_zero += 1
                    if (pred_cp > 0 and actual_cp > 0) or (pred_cp < 0 and actual_cp < 0):
                        sign_matches_nn += 1
                    if (mat_cp > 0 and actual_cp > 0) or (mat_cp < 0 and actual_cp < 0):
                        sign_matches_mat += 1

        # Summary Metrics
        nn_mae = float(np.mean(nn_errors_cp)) if nn_errors_cp else 0.0
        nn_rmse = float(np.sqrt(np.mean(np.square(nn_errors_cp)))) if nn_errors_cp else 0.0

        mat_mae = float(np.mean(material_errors_cp)) if material_errors_cp else 0.0
        mat_rmse = float(np.sqrt(np.mean(np.square(material_errors_cp)))) if material_errors_cp else 0.0

        # Pearson correlation
        if len(actual_cps) > 1 and np.std(actual_cps) > 0 and np.std(pred_cps) > 0:
            corr = float(np.corrcoef(actual_cps, pred_cps)[0, 1])
        else:
            corr = 0.0

        nn_sign_acc = (sign_matches_nn / total_non_zero) if total_non_zero > 0 else 1.0
        mat_sign_acc = (sign_matches_mat / total_non_zero) if total_non_zero > 0 else 1.0

        # Phase breakdowns
        phase_metrics = {}
        for p, d in phase_data.items():
            if d["nn"]:
                phase_metrics[p] = {
                    "nn_mae": round(float(np.mean(d["nn"])), 2),
                    "material_mae": round(float(np.mean(d["material"])), 2),
                    "count": len(d["nn"]),
                }

        return {
            "sample_count": len(test_records),
            "neural_network": {
                "mae_centipawns": round(nn_mae, 2),
                "rmse_centipawns": round(nn_rmse, 2),
                "correlation": round(corr, 4),
                "sign_accuracy": round(nn_sign_acc, 4),
            },
            "material_baseline": {
                "mae_centipawns": round(mat_mae, 2),
                "rmse_centipawns": round(mat_rmse, 2),
                "sign_accuracy": round(mat_sign_acc, 4),
            },
            "phase_breakdown": phase_metrics,
        }

    @staticmethod
    def generate_markdown_report(metrics: Dict[str, Any], model_type: str) -> str:
        """Generate a GitHub-flavored Markdown evaluation report for neural position evaluation."""
        nn = metrics["neural_network"]
        mat = metrics["material_baseline"]

        lines = [
            f"# Module 5: Neural Chess Position Evaluation Benchmark ({model_type.upper()})",
            "",
            "## 1. Overall Performance on Held-Out Test Positions",
            f"- **Sample Count**: {metrics['sample_count']} positions (Grouped by `game_id` without overlap)",
            "- **Target Representation**: Continuous centipawn mapping via bounded $\\tanh(\\text{cp}/400.0)$",
            "",
            "| Evaluation Method | MAE (Centipawns) | RMSE (Centipawns) | Sign Accuracy | Correlation ($r$) |",
            "| :--- | :---: | :---: | :---: | :---: |",
            f"| **Neural Network ({model_type.upper()})** | **{nn['mae_centipawns']:.1f}** | **{nn['rmse_centipawns']:.1f}** | **{nn['sign_accuracy']:.2%}** | **{nn['correlation']:.4f}** |",
            f"| **Material Baseline** | {mat['mae_centipawns']:.1f} | {mat['rmse_centipawns']:.1f} | {mat['sign_accuracy']:.2%} | Baseline |",
            "",
            "## 2. Game Phase Breakdown (Opening vs. Middlegame vs. Endgame)",
            "",
            "| Game Phase | Positions | Neural MAE (cp) | Material MAE (cp) | Improvement |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]

        for p, d in metrics.get("phase_breakdown", {}).items():
            delta = d["material_mae"] - d["nn_mae"]
            imp_str = f"+{delta:.1f} cp better" if delta > 0 else f"{delta:.1f} cp"
            lines.append(f"| **{p.capitalize()}** | {d['count']} | {d['nn_mae']:.1f} | {d['material_mae']:.1f} | {imp_str} |")

        lines.extend([
            "",
            "## 3. Methodological Comparison (Module 4 ML vs. Module 5 Deep Learning)",
            "- **Module 4 (Classical ML)**: Predicts *candidate move quality* given a position and candidate move. Learns tabular features (checks, captures, destination safety, piece-square tables) using XGBoost.",
            "- **Module 5 (Deep Learning)**: Evaluates *whole board state strength* directly from raw 18-channel spatial bitboards. Learns non-linear spatial representations through convolutional residual blocks without human-engineered feature heuristics.",
            "",
            "## 4. Limitations & Distribution Shift",
            "- Neural evaluations trained on master games reflect positional conventions from competitive tournament play.",
            "- In extreme tactical positions (e.g. forced checkmate in 5), deep alpha-beta search or Stockfish remains necessary to verify concrete tactical sequences.",
        ])

        return "\n".join(lines)

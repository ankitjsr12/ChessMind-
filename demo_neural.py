"""Demonstration script for Module 5: Neural Chess Position Evaluation.

Showcases:
1. Loading trained PyTorch neural network checkpoint (CNN with Residual Blocks).
2. Estimating position strength in centipawns and win probabilities.
3. Candidate move ranking through post-move neural evaluation.
4. Tactical position evaluations (Scholar's Mate, material imbalances).
5. Comparing Neural Evaluation with Material Baselines.
6. Explaining the distinction between Module 4 ML vs Module 5 Deep Learning.
"""

import json
import os
import chess
from backend.deep_learning import (
    BoardEncoder,
    NeuralEvaluatorBenchmark,
    NeuralPositionEvaluator,
    DeepLearningDataPipeline,
)


def main() -> None:
    print("=" * 80)
    print("ChessMind AI — Module 5: Neural Chess Position Evaluation")
    print("=" * 80)

    checkpoint_path = os.path.join("models", "neural", "best_evaluator.pt")
    evaluator = NeuralPositionEvaluator(checkpoint_path=checkpoint_path)

    if not evaluator.is_trained:
        print(f"Warning: Model not found at '{checkpoint_path}'. Please run training first.")
        return

    print(f"\n[1] Neural Network Checkpoint Loaded:")
    print(f"  Model Architecture:  {evaluator.model_type.upper()} with Residual Blocks")
    print(f"  Compute Device:      {evaluator.device}")
    print(f"  Input Representation: 18-plane (18, 8, 8) Tensor")
    print(f"  Validation Loss:     {evaluator.best_val_loss:.5f}")

    # Scenario 1: Standard Opening Position Evaluation
    fen_opening = chess.STARTING_FEN
    print(f"\n[2] Evaluating Starting Position (FEN: {fen_opening}):")
    eval_start = evaluator.evaluate_position(fen_opening)
    print(f"  White Evaluation:    {eval_start['display_text']} ({eval_start['eval_white_cp']} cp)")
    print(f"  Relative Evaluation: {eval_start['eval_relative_cp']} cp")
    print(f"  White Win Prob:      {eval_start['white_win_probability']:.2%}")
    print(f"  Evaluation Source:   {eval_start['source']}")

    # Scenario 2: Candidate Move Ranking via Neural State Simulation
    opening_candidates = ["e2e4", "d2d4", "g1f3", "c2c4", "a2a3", "h2h4"]
    print(f"\n[3] Candidate Move Ranking via Neural Position Simulation:")
    ranked_candidates = evaluator.evaluate_candidate_moves(fen_opening, candidate_moves=opening_candidates)

    print("-" * 80)
    print(f"{'Rank':<6}{'Move (SAN)':<12}{'Move (UCI)':<12}{'Player Eval':<15}{'Win Probability':<18}{'Capture/Check'}")
    print("-" * 80)
    for c in ranked_candidates:
        cap_chk = f"Cap: {c['is_capture']}, Chk: {c['is_check']}"
        print(f"{c['rank']:<6}{c['move_san']:<12}{c['move_uci']:<12}{c['display_text']:<15}{c['player_win_prob']:<18.2%}{cap_chk}")

    # Scenario 3: Asymmetric / Tactical Position Evaluations
    print(f"\n[4] Tactical and Material Imbalance Scenarios:")
    test_positions = [
        ("White Up a Queen", "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "White should have decisive advantage"),
        ("Scholar's Mate in 1", "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1", "White threatening Qxf7#"),
        ("Black Up a Minor Piece", "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1", "Black active knight"),
    ]

    for label, fen, note in test_positions:
        res = evaluator.evaluate_position(fen)
        print(f"  Position: {label:<22} | White Eval: {res['display_text']:<8} | Win Prob: {res['white_win_probability']:.1%} | ({note})")

    # Scenario 4: Comparison between Module 4 ML and Module 5 Deep Learning
    print(f"\n[5] Module 4 (Classical ML) vs Module 5 (Deep Learning) Comparison:")
    print("  -----------------------------------------------------------------------------")
    print("  Aspect                 Module 4 (Classical ML)       Module 5 (Deep Learning)")
    print("  -----------------------------------------------------------------------------")
    print("  Core Task:             Candidate Move Quality        Whole Position Strength")
    print("  Model Class:           XGBoost / Random Forest       PyTorch ConvNet (Residual)")
    print("  Input Features:        37 Engineered tabular feats   18x8x8 Spatial Bitboards")
    print("  Feature Extraction:    Heuristic (Material, King)    Learned 2D Spatial Convolutions")
    print("  Primary Metric:        Top-1 Candidate Move Match    Centipawn MAE / RMSE")
    print("  Lookahead Required:    None (Single move scoring)    Simulated board states")
    print("  -----------------------------------------------------------------------------")

    print("\n" + "=" * 80)
    print("Module 5 Neural Chess Position Evaluation demonstration completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()

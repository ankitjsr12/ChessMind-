"""Demonstration script for Module 4: Machine Learning Candidate Move Quality Prediction.

Showcases:
1. Loading trained ML model checkpoint and inspecting model metadata.
2. Ranking legal candidate moves on opening and tactical positions.
3. Categorizing moves into intuitive quality tiers (EXCELLENT, GOOD, INACCURACY, MISTAKE, BLUNDER).
4. Demonstrating feature highlights and source distinction (ML vs Engine).
5. Exporting structured JSON analysis reports.
"""

import json
import os
from backend.ml import MLMoveQualityPredictor, ModelNotTrainedError


def main() -> None:
    print("=" * 80)
    print("ChessMind AI — Module 4: ML Candidate Move Quality Prediction")
    print("=" * 80)

    model_path = os.path.join("models", "candidate_quality_model.joblib")
    predictor = MLMoveQualityPredictor(model_path=model_path)

    if not predictor.is_trained:
        print(f"Warning: Model not trained at {model_path}. Please run train pipeline first.")
        return

    print(f"\n[1] Loaded Model Checkpoint:")
    print(f"  Model Architecture: {predictor.model_name}")
    print(f"  Model Version:      {predictor.model_version}")
    print(f"  Features Utilized:  {len(predictor.feature_names)} features")
    metrics = predictor.model_bundle.get("test_metrics", {})
    if metrics:
        print(f"  Test Accuracy:      {metrics.get('accuracy', 0):.2%}")
        print(f"  Test ROC-AUC:       {metrics.get('roc_auc', 0):.4f}")
        print(f"  Top-1 Rank Match:   {metrics.get('top1_move_accuracy', 0):.2%}")

    # Scenario 1: Standard Opening Position Candidate Moves
    fen_opening = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    opening_candidates = ["e2e4", "d2d4", "g1f3", "c2c4", "a2a3", "h2h4"]

    print(f"\n[2] Evaluating Opening Candidates (FEN: {fen_opening}):")
    report1 = predictor.predict_move_quality(fen_opening, candidate_moves=opening_candidates)

    print(f"  Inference Time: {report1.inference_time_ms:.2f}ms")
    print(f"  Best Move: {report1.best_move_san} ({report1.best_move_uci})")
    print("-" * 80)
    print(f"{'Rank':<6}{'Move (SAN)':<12}{'Move (UCI)':<12}{'ML Score':<12}{'Quality Tier':<15}{'Top Pick?'}")
    print("-" * 80)
    for c in report1.candidates:
        top_str = "★ BEST" if c.is_top_recommendation else ""
        print(f"{c.rank:<6}{c.move_san:<12}{c.move_uci:<12}{c.quality_score:<12.4f}{c.quality_tier.value.upper():<15}{top_str}")

    # Scenario 2: Tactical Middlegame Position
    # Italian game: White can play d2d3, c2c3, O-O, or blunder with a2a3
    fen_tactical = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    tactical_candidates = ["e1g1", "d2d3", "c2c3", "b1c3", "h2h3", "a2a3"]

    print(f"\n[3] Tactical Middlegame Position:")
    print(f"  FEN: {fen_tactical}")
    report2 = predictor.predict_move_quality(fen_tactical, candidate_moves=tactical_candidates)
    print(f"  Inference Time: {report2.inference_time_ms:.2f}ms")
    print(f"  Recommended Move: {report2.best_move_san} ({report2.best_move_uci})")
    print("-" * 80)
    print(f"{'Rank':<6}{'Move (SAN)':<12}{'Move (UCI)':<12}{'ML Score':<12}{'Quality Tier':<15}{'Features'}")
    print("-" * 80)
    for c in report2.candidates:
        feat_str = f"Piece: {c.feature_highlights.get('moving_piece', '')}, Castle: {c.is_castling}"
        print(f"{c.rank:<6}{c.move_san:<12}{c.move_uci:<12}{c.quality_score:<12.4f}{c.quality_tier.value.upper():<15}{feat_str}")

    # Scenario 3: Structured JSON Output Preview
    print("\n[4] Structured JSON Output Preview:")
    sample_json = json.dumps(report1.to_dict(), indent=2)
    lines = sample_json.splitlines()
    print("\n".join(lines[:32]))
    print(f"  ... [truncated {len(lines) - 32} lines of JSON schema] ...")

    print("\n" + "=" * 80)
    print("Module 4 ML Candidate Move Quality demonstration completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()

"""Demonstration script for Module 3: Opponent Move Prediction.

Showcases:
1. Evaluating candidate moves and predicting the opponent's adversarial replies.
2. Principal variations (PV) and tactical consequence analysis (checks, captures, mates).
3. Punishing candidate blunders vs finding winning refutations.
4. Alpha-Beta pruning vs Pure Minimax efficiency comparison (node counts & time reduction).
5. Comprehensive JSON serialization output matching required schemas.
"""

import json
import chess
from backend.opponent_prediction import (
    OpponentSearchEngine,
    PredictionType,
    PositionEvaluator,
)

def main() -> None:
    print("=" * 80)
    print("ChessMind AI — Module 3: Opponent Move Prediction Demonstration")
    print("=" * 80)

    engine = OpponentSearchEngine(default_depth=3, default_time_limit=2.0)

    # 1. Candidate Consequence Analysis on a Tactical Middlegame Position
    # Position: White to move. Candidates: Bxf6 (capturing knight), Nd5 (centralizing), a3 (quiet)
    tactical_fen = "r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/2N2N2/PP2PPPP/R2QKB1R w KQ - 2 7"
    candidates = ["e2e3", "c4d5", "d1b3"]
    print(f"\n[1] Examining Candidate Moves on Middlegame Position:")
    print(f"FEN: {tactical_fen}")
    print(f"Candidate Moves To Examine: {candidates}")

    report = engine.analyze_candidate_consequences(
        fen_or_engine=tactical_fen,
        candidate_moves=candidates,
        depth=3,
    )

    print(f"\nActive Player: {report.side_to_move.value.upper()} | Opponent: {report.opponent_side.value.upper()}")
    print(f"Total Nodes Evaluated: {report.total_nodes:,} | Search Time: {report.total_duration_ms:.2f}ms")
    print("-" * 80)
    print(f"{'Candidate':<12}{'Eval':<10}{'Predicted Opponent Response':<28}{'Tactical Threat':<18}{'Opp PV'}")
    print("-" * 80)

    for c in report.consequences:
        cand_str = f"{c.candidate_move_san} ({c.candidate_move_uci})"
        eval_str = c.post_candidate_evaluation.display_text
        if c.predicted_opponent_response:
            opp = c.predicted_opponent_response
            opp_str = f"{opp.move_san} ({opp.move_uci})"
            threat_str = opp.tactical_threat or "Positional"
            pv_preview = " ".join(opp.pv_san[:3])
        else:
            opp_str = "None (Terminal)"
            threat_str = "Checkmate"
            pv_preview = "-"
        print(f"{cand_str:<12}{eval_str:<10}{opp_str:<28}{threat_str:<18}{pv_preview}")

    # 2. Detecting Checkmate in 1 & Opponent Inability to Respond
    mate_in_one_fen = "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"
    print("\n[2] Tactical Position with Forced Checkmate (Scholar's Mate):")
    print(f"Testing Candidate Qxf7# vs Quiet Move d2d3")
    mate_report = engine.analyze_candidate_consequences(
        fen_or_engine=mate_in_one_fen,
        candidate_moves=["h5f7", "d2d3"],
        depth=2,
    )

    for c in mate_report.consequences:
        print(f"\n  Candidate: {c.candidate_move_san} ({c.candidate_move_uci})")
        print(f"  Post-Candidate Eval: {c.post_candidate_evaluation.display_text}")
        print(f"  Is Forced Mate: {c.is_forced_mate} (Mate in {c.mate_in} ply)")
        if c.predicted_opponent_response:
            print(f"  Predicted Opponent Response: {c.predicted_opponent_response.move_san}")
        else:
            print("  Predicted Opponent Response: None (Game Terminated / Opponent Checkmated)")

    # 3. Blunder Punishment Detection
    # Fool's Mate setup: Black has Qh4#. What if White considers g2g4 vs d2d4?
    fools_fen = "rnbqkbnr/pppp1ppp/4p3/8/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
    print("\n[3] Blunder Punishment Analysis (Adversarial Refutation):")
    print(f"Black to move: Candidates Qh4# (checkmate) vs d7d5 (quiet)")
    fools_report = engine.analyze_candidate_consequences(
        fen_or_engine=fools_fen,
        candidate_moves=["d8h4", "d7d5"],
        depth=2,
    )
    for c in fools_report.consequences:
        print(f"  Move: {c.candidate_move_san} | Eval: {c.post_candidate_evaluation.display_text} | Forced Mate: {c.is_forced_mate}")

    # 4. Search Efficiency Benchmark: Pure Minimax vs Alpha-Beta Pruning
    print("\n[4] Search Efficiency Benchmark (Pure Minimax vs. Alpha-Beta Pruning):")
    bench_board = chess.Board("r1bqk2r/pppp1ppp/2n5/4p3/1b2P3/2NP1N2/PPPB1PPP/R2QKB1R w KQkq - 0 6")
    
    # Alpha-Beta
    engine.nodes_evaluated = 0
    score_ab, pv_ab = engine.negamax(bench_board, depth=2, alpha=-100000, beta=100000)
    ab_nodes = engine.nodes_evaluated

    # Pure Minimax
    score_pure, pure_nodes = engine.search_without_pruning(bench_board, depth=2)
    saved_nodes = pure_nodes - ab_nodes
    pct_saved = (saved_nodes / pure_nodes) * 100

    print(f"  Target Position: Tactical Italian Game Fork")
    print(f"  Pure Minimax Nodes Evaluated: {pure_nodes:,}")
    print(f"  Alpha-Beta Nodes Evaluated:   {ab_nodes:,}")
    print(f"  Nodes Pruned (Saved):         {saved_nodes:,} ({pct_saved:.1f}% reduction)")
    print(f"  Scores Match Exactly:         {score_ab == score_pure} (Score = {score_ab})")

    # 5. Schema Serialization Sample
    print("\n[5] Structured JSON Schema Output Sample:")
    sample_json = json.dumps(report.to_dict(), indent=2)
    lines = sample_json.splitlines()
    print("\n".join(lines[:35]))
    print(f"  ... [truncated {len(lines) - 35} lines of JSON schema] ...")
    print("\n" + "=" * 80)
    print("Module 3 Opponent Move Prediction demonstration finished successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()

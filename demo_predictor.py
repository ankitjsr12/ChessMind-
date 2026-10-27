"""Demonstration script for Module 2: Best Move Predictor.

Showcases:
1. Position evaluation with best move and 3 candidate alternatives.
2. Structured JSON output.
3. Tactical positions (mate in 1).
4. Terminal position handling (Checkmate, Stalemate).
5. Side-by-side comparison between Stockfish and Minimax search baseline.
"""

import json
from backend.predictor import MoveRanker, MinimaxEngine, StockfishService

def main() -> None:
    print("=" * 70)
    print("ChessMind AI — Module 2: Best Move Predictor Demonstration")
    print("=" * 70)

    ranker = MoveRanker()

    # 1. Standard Opening Position Analysis
    fen_opening = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    print("\n[1] Evaluating Standard Starting Position (Candidate Count: 4):")
    analysis = ranker.predict_best_moves(fen_opening, candidate_count=4)
    print(f"Engine: {analysis.engine_name}")
    print(f"Side to move: {analysis.side_to_move.value}")
    print(f"Best Move: {analysis.best_move_san} ({analysis.best_move_uci})")
    print(f"Search Depth: {analysis.search_depth} | Nodes: {analysis.nodes_evaluated} | Time: {analysis.analysis_time_ms:.1f}ms")
    print("-" * 50)
    print(f"{'Rank':<6}{'Move (SAN)':<12}{'Move (UCI)':<12}{'Eval':<10}{'PV Continuation'}")
    print("-" * 50)
    for c in analysis.candidates:
        pv_str = " ".join(c.pv_san[:4])
        print(f"{c.rank:<6}{c.san:<12}{c.uci:<12}{c.evaluation.display_text:<10}{pv_str}")

    # 2. Tactical Mate in 1 Position
    fen_mate = "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"
    print("\n[2] Tactical Position (Scholar's Mate in 1):")
    mate_analysis = ranker.predict_best_moves(fen_mate, candidate_count=3)
    print(f"Best Move: {mate_analysis.best_move_san} ({mate_analysis.best_move_uci})")
    top_cand = mate_analysis.candidates[0]
    print(f"Top Evaluation: {top_cand.evaluation.display_text} (Score Type: {top_cand.evaluation.score_type.value})")

    # 3. Terminal Position Handling (Checkmate)
    fen_terminal = "rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 1"
    print("\n[3] Handling Terminal Position (Checkmate already on board):")
    term_res = ranker.predict_best_moves(fen_terminal)
    print(f"Status: {term_res.engine_status.value}")
    print(f"Is Terminal: {term_res.is_terminal} | Reason: {term_res.terminal_reason}")
    print(f"Candidates Count: {len(term_res.candidates)}")

    # 4. Engine Comparison Interface (Stockfish vs Minimax)
    print("\n[4] Engine Comparison Interface (Stockfish vs Minimax):")
    fen_tactical = "r1bq1rk1/ppp2ppp/2np1n2/1B2p3/1b2P3/2NP1N2/PPPB1PPP/R2QK2R w KQ - 0 7"
    comparison = ranker.compare_stockfish_and_minimax(fen_tactical, candidate_count=3)
    print(f"Summary: {comparison.summary}")
    print(f"Minimax Recommended: {comparison.minimax_analysis.best_move_san} ({comparison.minimax_analysis.best_move_uci})")
    if comparison.stockfish_analysis:
        print(f"Stockfish Recommended: {comparison.stockfish_analysis.best_move_san} ({comparison.stockfish_analysis.best_move_uci})")

    # 5. JSON Output Format
    print("\n[5] Structured JSON Output Preview:")
    json_output = json.dumps(analysis.to_dict(), indent=2)
    print(json_output[:600] + "\n  ...\n}")

    print("\nDemonstration completed successfully!")

if __name__ == "__main__":
    main()

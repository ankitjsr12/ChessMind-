"""Interactive demonstration script for Module 1: Chess Engine.

Demonstrates:
- Starting a game
- Playing moves in SAN and UCI notation
- Move undoing
- Board state extraction and inspection
- ASCII board rendering
- PGN export
- ML Tensor extraction
- AI move execution using BaseMovePredictor
"""

from typing import List, Optional
from backend.chess_engine import ChessEngine, BaseMovePredictor


class GreedyRandomAI(BaseMovePredictor):
    """Simple demo AI that prioritizes captures, otherwise plays first legal move."""

    def predict_move(self, fen: str, legal_moves_uci: List[str]) -> Optional[str]:
        if not legal_moves_uci:
            return None
        # Return first legal move for deterministic demo
        return legal_moves_uci[0]


def main() -> None:
    print("=" * 60)
    print("ChessMind AI — Module 1: Core Engine Demonstration")
    print("=" * 60)

    # 1. Initialize engine
    engine = ChessEngine()
    print("\n[1] Initial Board (Standard FEN):")
    print(engine.render_ascii())
    print(f"Turn: {engine.turn.value}")
    print(f"Total legal moves: {len(engine.get_legal_moves_uci())}")

    # 2. Make standard moves
    print("\n[2] Playing moves: 1. e4 e5 2. Nf3 Nc6 3. Bc4...")
    engine.make_move("e4")     # SAN
    engine.make_move("e7e5")   # UCI
    engine.make_move("Nf3")    # SAN
    engine.make_move("b8c6")   # UCI
    engine.make_move("Bc4")    # SAN

    print(engine.render_ascii())
    print(f"\nCurrent FEN: {engine.fen}")
    print(f"UCI Move History: {engine.get_uci_history()}")
    print(f"SAN Move History: {engine.get_san_history()}")

    # 3. Undo move
    print("\n[3] Undoing last move (Bc4)...")
    undone = engine.undo_move()
    print(f"Undone move: {undone.san} ({undone.uci})")
    print(f"Current Turn: {engine.turn.value}")
    print(f"History length: {len(engine.get_move_history())}")

    # Re-apply move
    engine.make_move("Bc4")

    # 4. Board state inspection
    print("\n[4] Inspecting BoardState Model:")
    state = engine.get_board_state()
    print(f"Is in check: {state.is_check}")
    print(f"Is checkmate: {state.is_checkmate}")
    print(f"Is game over: {state.is_game_over}")
    print(f"White castling rights: Kingside={state.castling_rights.white_kingside}, Queenside={state.castling_rights.white_queenside}")
    print(f"Piece counts: White Pawns={state.piece_counts['P']}, Black Knights={state.piece_counts['n']}")

    # 5. Play AI Move
    print("\n[5] Executing AI Opponent Move:")
    ai = GreedyRandomAI()
    ai_result = engine.play_ai_move(ai)
    print(f"AI played: {ai_result.move_record.san} ({ai_result.move_record.uci})")
    print(engine.render_ascii())

    # 6. ML / Deep Learning feature representations
    print("\n[6] Feature Extraction for ML / Deep Learning:")
    bitboards = engine.get_bitboard_planes()
    print(f"Bitboard planes extracted: {len(bitboards)} planes")
    print(f"White Pawns Bitmask: {hex(bitboards['P'])}")

    tensor = engine.get_tensor_representation()
    print(f"Spatial Tensor planes: {len(tensor)} channels of 8x8 (shape: 14x8x8)")
    print(f"Stockfish UCI position command: {engine.get_stockfish_position_command()}")

    # 7. Export PGN
    print("\n[7] Exporting Game to PGN:")
    pgn_str = engine.export_pgn(
        headers={
            "Event": "ChessMind AI Showcase",
            "White": "Player One",
            "Black": "GreedyRandomAI",
        }
    )
    print(pgn_str)

    print("\nDemonstration completed successfully!")


if __name__ == "__main__":
    main()

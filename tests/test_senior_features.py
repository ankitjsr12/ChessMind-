"""Unit tests for Senior Development Features:

1. ECO Opening Book & Position Identification
2. Production PGN Parsing & Validation
3. Explainable Tactical Blunder Detection & Classification
"""

import pytest
import chess
from backend.chess_engine import opening_book, pgn_service, blunder_detector


def test_opening_identification_sicilian_najdorf():
    moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]
    entry = opening_book.identify_opening(moves)
    assert entry.eco == "B90"
    assert "Najdorf" in entry.name


def test_opening_candidate_continuations():
    # After 1. e4 e5
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")
    continuations = opening_book.get_candidate_book_moves(board.fen())
    assert len(continuations) > 0
    sans = [c["san"] for c in continuations]
    assert "Nf3" in sans or "f4" in sans


def test_pgn_service_parsing():
    pgn_sample = """[Event "Casual Game"]
[Site "ChessMind Arena"]
[Date "2026.11.02"]
[Round "1"]
[White "Morphy"]
[Black "Duke"]
[Result "1-0"]
[ECO "C41"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 1-0"""

    parsed = pgn_service.parse_pgn_text(pgn_sample)
    assert parsed["white"] == "Morphy"
    assert parsed["black"] == "Duke"
    assert parsed["result"] == "1-0"
    assert len(parsed["moves_san"]) == 6
    assert parsed["moves_san"] == ["e4", "e5", "Nf3", "d6", "d4", "Bg4"]


def test_blunder_detector_optimal_move():
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    board_after = board.copy()
    board_after.push(move)

    res = blunder_detector.classify_move(
        board_before=board,
        move=move,
        board_after=board_after,
        played_cp=30.0,
        best_cp=35.0,
        best_move=move,
    )
    assert res["quality"] in ("best", "good")
    assert res["cp_loss"] <= 15.0
    assert res["accuracy"] >= 90.0


def test_blunder_detector_blunder_classification():
    board = chess.Board()
    # Move e2e4 then Black plays f7f6, then White plays d2d4, Black plays g7g5, White plays d1h5# (Scholar's/Fool's mate)
    board.push_san("f3")
    board.push_san("e5")
    board.push_san("g4")
    move = board.parse_san("Qh4#")
    board_after = board.copy()
    board_after.push(move)

    res = blunder_detector.classify_move(
        board_before=board,
        move=move,
        board_after=board_after,
        played_cp=10000.0,
        best_cp=10000.0,
        best_move=move,
    )
    assert res["is_checkmate"] is True
    assert res["quality"] == "best"


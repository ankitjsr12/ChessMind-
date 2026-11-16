"""Encyclopedia of Chess Openings (ECO) Database and Opening Explorer.

Provides robust opening identification, ECO classification, and opening book candidate moves
for ChessMind AI. Matches move sequences and FEN positions against master-level openings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import chess


@dataclass
class OpeningEntry:
    """Represents a categorized chess opening in the ECO catalog."""
    eco: str
    name: str
    moves_san: List[str]
    moves_uci: List[str] = field(default_factory=list)
    fen: str = ""

    def __post_init__(self):
        if not self.moves_uci and self.moves_san:
            # Generate UCI representation and FEN
            b = chess.Board()
            uci_list = []
            for san in self.moves_san:
                try:
                    m = b.parse_san(san)
                    uci_list.append(m.uci())
                    b.push(m)
                except Exception:
                    break
            self.moves_uci = uci_list
            if not self.fen:
                self.fen = b.fen()


# Master ECO Catalog covering key opening branches and variations
ECO_OPENING_DEFINITIONS: List[Tuple[str, str, List[str]]] = [
    # --- C: Open Games (1.e4 e5) & French Defense ---
    ("C50", "Italian Game: Giuoco Piano", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]),
    ("C51", "Evans Gambit", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4"]),
    ("C55", "Two Knights Defense", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"]),
    ("C57", "Fried Liver Attack", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5", "Nxf7"]),
    ("C60", "Ruy Lopez (Spanish Opening)", ["e4", "e5", "Nf3", "Nc6", "Bb5"]),
    ("C65", "Ruy Lopez: Berlin Defense", ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6"]),
    ("C70", "Ruy Lopez: Morphy Defense", ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4"]),
    ("C88", "Ruy Lopez: Closed", ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7", "Re1", "b5", "Bb3", "d6"]),
    ("C45", "Scotch Game", ["e4", "e5", "Nf3", "Nc6", "d4", "exd4", "Nxd4"]),
    ("C42", "Petrov's Defense (Russian Game)", ["e4", "e5", "Nf3", "Nf6"]),
    ("C44", "King's Pawn Game: Ponziani Opening", ["e4", "e5", "Nf3", "Nc6", "c3"]),
    ("C47", "Four Knights Game: Scotch Variation", ["e4", "e5", "Nf3", "Nc6", "Nc3", "Nf6", "d4"]),
    ("C30", "King's Gambit", ["e4", "e5", "f4"]),
    ("C33", "King's Gambit Accepted", ["e4", "e5", "f4", "exf4"]),
    ("C20", "King's Pawn Game", ["e4", "e5"]),
    ("C10", "French Defense", ["e4", "e6", "d4", "d5"]),
    ("C11", "French Defense: Classical", ["e4", "e6", "d4", "d5", "Nc3", "Nf6"]),
    ("C02", "French Defense: Advance Variation", ["e4", "e6", "d4", "d5", "e5"]),
    ("C00", "French Defense", ["e4", "e6"]),

    # --- B: Semi-Open Games (Sicilian, Caro-Kann, Scandinavian, Pirc) ---
    ("B90", "Sicilian Defense: Najdorf Variation", ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]),
    ("B70", "Sicilian Defense: Dragon Variation", ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6"]),
    ("B80", "Sicilian Defense: Scheveningen Variation", ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "e6"]),
    ("B33", "Sicilian Defense: Sveshnikov (Pelikan) Variation", ["e4", "c5", "Nf3", "Nc6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "e5"]),
    ("B22", "Sicilian Defense: Alapin Variation", ["e4", "c5", "c3"]),
    ("B23", "Sicilian Defense: Closed", ["e4", "c5", "Nc3"]),
    ("B50", "Sicilian Defense: Open", ["e4", "c5", "Nf3", "d6", "d4"]),
    ("B20", "Sicilian Defense", ["e4", "c5"]),
    ("B12", "Caro-Kann Defense: Advance Variation", ["e4", "c6", "d4", "d5", "e5"]),
    ("B13", "Caro-Kann Defense: Exchange Variation", ["e4", "c6", "d4", "d5", "exd5", "cxd5"]),
    ("B15", "Caro-Kann Defense: Classical / Tartakower", ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4"]),
    ("B10", "Caro-Kann Defense", ["e4", "c6"]),
    ("B01", "Scandinavian Defense", ["e4", "d5"]),
    ("B01", "Scandinavian Defense: Mieses-Kotroc", ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5"]),
    ("B02", "Alekhine's Defense", ["e4", "Nf6"]),
    ("B07", "Pirc Defense", ["e4", "d6", "d4", "Nf6", "Nc3", "g6"]),
    ("B06", "Modern Defense (Robatsch)", ["e4", "g6"]),

    # --- D: Closed Games (Queen's Gambit, Slav, Grunfeld) ---
    ("D06", "Queen's Gambit", ["d4", "d5", "c4"]),
    ("D20", "Queen's Gambit Accepted", ["d4", "d5", "c4", "dxc4"]),
    ("D30", "Queen's Gambit Declined", ["d4", "d5", "c4", "e6"]),
    ("D35", "Queen's Gambit Declined: Exchange", ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5"]),
    ("D10", "Slav Defense", ["d4", "d5", "c4", "c6"]),
    ("D15", "Slav Defense: Modern Line", ["d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3", "a6"]),
    ("D43", "Semi-Slav Defense", ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Nf3", "c6"]),
    ("D80", "Grünfeld Defense", ["d4", "Nf6", "c4", "g6", "Nc3", "d5"]),
    ("D85", "Grünfeld Defense: Exchange Variation", ["d4", "Nf6", "c4", "g6", "Nc3", "d5", "cxd5", "Nxd5", "e4", "Nxc3", "bxc3"]),
    ("D02", "Queen's Pawn Game: London System", ["d4", "d5", "Nf3", "Nf6", "Bf4"]),
    ("D00", "Queen's Pawn Game", ["d4", "d5"]),

    # --- E: Indian Defenses & Catalan ---
    ("E60", "King's Indian Defense", ["d4", "Nf6", "c4", "g6"]),
    ("E70", "King's Indian Defense: Classical", ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O"]),
    ("E97", "King's Indian: Mar del Plata Variation", ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5", "O-O", "Nc6", "d5", "Ne7"]),
    ("E20", "Nimzo-Indian Defense", ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]),
    ("E00", "Catalan Opening", ["d4", "Nf6", "c4", "e6", "g3"]),
    ("E06", "Catalan Opening: Closed", ["d4", "Nf6", "c4", "e6", "g3", "d5", "Bg2", "Be7", "Nf3", "O-O"]),
    ("E11", "Bogo-Indian Defense", ["d4", "Nf6", "c4", "e6", "Nf3", "Bb4+"]),
    ("E12", "Queen's Indian Defense", ["d4", "Nf6", "c4", "e6", "Nf3", "b6"]),

    # --- A: Flank Openings (English, Reti, Dutch, Benoni) ---
    ("A10", "English Opening", ["c4"]),
    ("A20", "English Opening: King's English", ["c4", "e5"]),
    ("A30", "English Opening: Symmetrical", ["c4", "c5"]),
    ("A04", "Réti Opening", ["Nf3"]),
    ("A09", "Réti Opening: Advance", ["Nf3", "d5", "c4"]),
    ("A80", "Dutch Defense", ["d4", "f5"]),
    ("A84", "Dutch Defense: Classical / Leningrad", ["d4", "f5", "c4", "Nf6", "g3"]),
    ("A56", "Benoni Defense", ["d4", "Nf6", "c4", "c5", "d5"]),
    ("A60", "Modern Benoni", ["d4", "Nf6", "c4", "c5", "d5", "e6", "Nc3", "exd5", "cxd5", "d6"]),
    ("A00", "Grob Opening", ["g4"]),
    ("A00", "Lasker's Simultaneous Opening", ["a3"]),
]


class OpeningBook:
    """Manages opening identification and book moves."""

    def __init__(self) -> None:
        self.entries: List[OpeningEntry] = []
        self._fen_map: Dict[str, OpeningEntry] = {}
        self._load_entries()

    def _load_entries(self) -> None:
        for eco, name, moves in ECO_OPENING_DEFINITIONS:
            entry = OpeningEntry(eco=eco, name=name, moves_san=moves)
            self.entries.append(entry)
            # Store simplified FEN (without en passant / halfmove clock) for robust matching
            simplified_fen = self._simplify_fen(entry.fen)
            self._fen_map[simplified_fen] = entry

    @staticmethod
    def _simplify_fen(fen: str) -> str:
        """Keep piece placement, active turn, and castling availability."""
        parts = fen.split()
        if len(parts) >= 3:
            return f"{parts[0]} {parts[1]} {parts[2]}"
        return fen

    def identify_opening(self, moves: List[str]) -> OpeningEntry:
        """Identify opening from a sequence of moves (SAN or UCI).

        Matches the longest possible sequence in the ECO database.
        Defaults to General Opening if no specific match is found.
        """
        if not moves:
            return OpeningEntry(eco="A00", name="Starting Position", moves_san=[])

        best_match: Optional[OpeningEntry] = None
        max_matched_length = 0

        # Try to parse all moves into SAN representation
        board = chess.Board()
        san_moves: List[str] = []
        for m in moves:
            try:
                move_obj = board.parse_san(m) if m in [board.san(leg) for leg in board.legal_moves] else chess.Move.from_uci(m)
                san_moves.append(board.san(move_obj))
                board.push(move_obj)
            except Exception:
                break

        # Check against entry database
        for entry in self.entries:
            entry_len = len(entry.moves_san)
            if entry_len <= len(san_moves):
                if san_moves[:entry_len] == entry.moves_san:
                    if entry_len > max_matched_length:
                        max_matched_length = entry_len
                        best_match = entry

        if best_match:
            return best_match

        # Heuristic fallback based on initial moves
        if san_moves:
            first = san_moves[0]
            if first == "e4":
                if len(san_moves) > 1 and san_moves[1] == "e5":
                    return OpeningEntry(eco="C20", name="King's Pawn Game", moves_san=san_moves[:2])
                return OpeningEntry(eco="B00", name="King's Pawn Opening", moves_san=san_moves[:1])
            elif first == "d4":
                if len(san_moves) > 1 and san_moves[1] == "d5":
                    return OpeningEntry(eco="D00", name="Queen's Pawn Game", moves_san=san_moves[:2])
                return OpeningEntry(eco="A40", name="Queen's Pawn Opening", moves_san=san_moves[:1])
            elif first == "c4":
                return OpeningEntry(eco="A10", name="English Opening", moves_san=san_moves[:1])
            elif first == "Nf3":
                return OpeningEntry(eco="A04", name="Réti Opening", moves_san=san_moves[:1])

        return OpeningEntry(eco="A00", name="Standard Game", moves_san=san_moves)

    def get_candidate_book_moves(self, current_fen: str) -> List[Dict[str, Any]]:
        """Find known book continuations from the current position.

        Returns candidate moves with their continuation names and ECO codes.
        """
        board = chess.Board(current_fen)
        simplified = self._simplify_fen(board.fen())

        candidate_moves: List[Dict[str, Any]] = []
        seen_moves: set = set()

        for entry in self.entries:
            # Check if this position is a prefix of entry
            test_board = chess.Board()
            for idx, san in enumerate(entry.moves_san):
                if self._simplify_fen(test_board.fen()) == simplified:
                    # The next move is in this book entry
                    try:
                        next_move = test_board.parse_san(san)
                        if next_move.uci() not in seen_moves:
                            seen_moves.add(next_move.uci())
                            candidate_moves.append({
                                "san": san,
                                "uci": next_move.uci(),
                                "eco": entry.eco,
                                "variation": entry.name,
                                "depth_in_book": idx + 1,
                            })
                    except Exception:
                        pass
                    break
                try:
                    m = test_board.parse_san(san)
                    test_board.push(m)
                except Exception:
                    break

        return candidate_moves


# Global singleton opening book instance
opening_book = OpeningBook()


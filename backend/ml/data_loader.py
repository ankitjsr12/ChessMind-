"""Dataset loader and PGN processor for ChessMind AI Machine Learning.

DATASET METADATA:
- Source: Lichess Open Game Database & Historical World Champion / Master Games
- License: Creative Commons CC0 1.0 Universal / Public Domain Dedication
- Format: Portable Game Notation (PGN)
- Scope: High-level chess games with full move histories and standard tournament rules.

PREPROCESSING PIPELINE:
1. Parse games sequentially using python-chess pgn reader.
2. Filter out malformed games, games with fewer than 10 moves, or invalid positions.
3. Skip opening book moves (first 4 plies) to focus on genuine tactical and positional choices.
4. For each selected position, extract:
   - Positive example: The move played by the master (is_quality_move = 1)
   - Negative/suboptimal examples: Sampled legal candidate alternatives (is_quality_move = 0)
5. Group all generated examples by unique `game_id` to prevent data leakage across train/test splits.
"""

import io
import logging
from typing import Dict, Generator, List, Optional, Tuple, Union
import chess
import chess.pgn
import pandas as pd

logger = logging.getLogger(__name__)

# Curated, public domain (CC0) master tournament games for standalone training & reproducible tests
SAMPLE_PUBLIC_DOMAIN_PGNS = """
[Event "London 1851 Immortal Game"]
[Site "London"]
[Date "1851.06.21"]
[Round "1"]
[White "Anderssen, Adolf"]
[Black "Kieseritzky, Lionel"]
[Result "1-0"]

1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5 8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8 15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6 21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0

[Event "Paris Opera Game"]
[Site "Paris"]
[Date "1858.11.02"]
[Round "1"]
[White "Morphy, Paul"]
[Black "Duke of Brunswick and Count Isouard"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0

[Event "Hastings 1895"]
[Site "Hastings"]
[Date "1895.08.17"]
[Round "1"]
[White "Steinitz, William"]
[Black "von Bardeleben, Curt"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 d5 8. exd5 Nxd5 9. O-O Be6 10. Bg5 Be7 11. Bxd5 Bxd5 12. Nxd5 Qxd5 13. Bxe7 Nxe7 14. Re1 f6 15. Qe2 Qd7 16. Rac1 c6 17. d5 cxd5 18. Nd4 Kf7 19. Ne6 Rhc8 20. Qg4 g6 21. Ng5+ Ke8 22. Rxe7+ Kf8 23. Rf7+ Kg8 24. Rg7+ Kh8 25. Rxh7+ 1-0

[Event "St. Petersburg 1914"]
[Site "St. Petersburg"]
[Date "1914.05.09"]
[Round "1"]
[White "Lasker, Emanuel"]
[Black "Capablanca, Jose Raul"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6 dxc6 5. d4 exd4 6. Qxd4 Qxd4 7. Nxd4 Bd6 8. Nc3 Ne7 9. O-O O-O 10. f4 Re8 11. Nb3 f6 12. f5 b6 13. Bf4 Bb7 14. Bxd6 cxd6 15. Rad1 Rad8 16. Nd4 Bc8 17. Rf2 d5 18. Ne6 Bxe6 19. fxe6 Rd6 20. exd5 cxd5 21. Re2 Red8 22. Kf2 Kf8 23. Rd3 1-0

[Event "Bled 1931"]
[Site "Bled"]
[Date "1931.09.08"]
[Round "1"]
[White "Alekhine, Alexander"]
[Black "Nimzowitsch, Aron"]
[Result "1-0"]

1. e4 e6 2. d4 d5 3. Nc3 Bb4 4. e5 c5 5. Bd2 Ne7 6. Nb5 Bxd2+ 7. Qxd2 O-O 8. c3 b6 9. f4 Ba6 10. Nf3 Qd7 11. a4 Nbc6 12. b4 cxb4 13. cxb4 Bb7 14. Nd6 f5 15. a5 Nc8 16. Nxb7 Qxb7 17. a6 Qe7 18. b5 Na5 19. Rb1 Qd7 20. Bd3 Ne7 21. O-O Rac8 22. Rfc1 Rxc1+ 23. Rxc1 Rc8 24. Rc3 1-0

[Event "World Championship Match 1972"]
[Site "Reykjavik"]
[Date "1972.07.23"]
[Round "6"]
[White "Fischer, Robert J"]
[Black "Spassky, Boris V"]
[Result "1-0"]

1. c4 e6 2. Nf3 d5 3. d4 Nf6 4. Nc3 Be7 5. Bg5 O-O 6. e3 h6 7. Bh4 b6 8. cxd5 Nxd5 9. Bxe7 Qxe7 10. Nxd5 exd5 11. Rc1 Be6 12. Qa4 c5 13. Qa3 Rc8 14. Bb5 a6 15. dxc5 bxc5 16. O-O Ra7 17. Be2 Nd7 18. Nd4 Qf8 19. Nxe6 fxe6 20. e4 d4 21. f4 Qe7 22. e5 Rb8 23. Bc4 Kh8 24. Qh3 Nf8 25. b3 a5 26. f5 exf5 27. Rxf5 Nh7 28. Rcf1 Qd8 29. Qg3 Re7 30. h4 Rbb7 31. e6 Rbc7 32. Qe5 Qe8 33. a4 Qd8 34. R1f2 Qe8 35. R2f3 Qd8 36. Bd3 Qe8 37. Qe4 Nf6 38. Rxf6 gxf6 39. Rxf6 Kg8 40. Bc4 Kh8 41. Qf4 1-0
"""


class ChessDataLoader:
    """Loads, validates, and extracts supervised training examples from chess games."""

    def __init__(
        self,
        min_game_plies: int = 12,
        skip_opening_plies: int = 4,
        max_positions_per_game: int = 15,
        candidate_alternatives_per_pos: int = 3,
        random_seed: int = 42,
    ) -> None:
        self.min_game_plies = min_game_plies
        self.skip_opening_plies = skip_opening_plies
        self.max_positions_per_game = max_positions_per_game
        self.candidate_alternatives_per_pos = candidate_alternatives_per_pos
        self.random_seed = random_seed

    def load_from_pgn_text(
        self,
        pgn_text: str,
        max_games: Optional[int] = None,
    ) -> pd.DataFrame:
        """Parse PGN text stream into position-level and move-level examples."""
        pgn_io = io.StringIO(pgn_text)
        return self._parse_pgn_stream(pgn_io, max_games=max_games)

    def load_from_pgn_file(
        self,
        filepath: str,
        max_games: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load games from an external PGN file."""
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return self._parse_pgn_stream(f, max_games=max_games)

    def load_sample_dataset(
        self,
        max_games: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load the bundled CC0 public domain master dataset."""
        return self.load_from_pgn_text(SAMPLE_PUBLIC_DOMAIN_PGNS, max_games=max_games)

    def _parse_pgn_stream(
        self,
        stream: io.TextIOBase,
        max_games: Optional[int] = None,
    ) -> pd.DataFrame:
        """Internal generator reading games and building tabular candidate move records."""
        records: List[Dict[str, Union[str, int, float, bool]]] = []
        game_idx = 0

        while True:
            if max_games is not None and game_idx >= max_games:
                break

            try:
                game = chess.pgn.read_game(stream)
            except Exception as e:
                logger.warning("Skipping malformed game at index %d: %s", game_idx, e)
                continue

            if game is None:
                break

            # Validate headers and minimal move length
            moves = list(game.mainline_moves())
            if len(moves) < self.min_game_plies:
                continue

            game_id = f"game_{game_idx:04d}_{game.headers.get('White', 'W')[:4]}_vs_{game.headers.get('Black', 'B')[:4]}"
            game_records = self._extract_examples_from_game(game_id, game)
            records.extend(game_records)
            game_idx += 1

        df = pd.DataFrame(records)
        return df

    def _extract_examples_from_game(
        self,
        game_id: str,
        game: chess.pgn.Game,
    ) -> List[Dict[str, Union[str, int, float, bool]]]:
        """Extract candidate move pairs (played master move vs legal alternative moves)."""
        examples: List[Dict[str, Union[str, int, float, bool]]] = []
        board = game.board()
        moves = list(game.mainline_moves())

        # Select positions skipping early opening plies
        valid_ply_indices = list(range(self.skip_opening_plies, len(moves)))
        if not valid_ply_indices:
            return []

        # Subsample if game has too many plies
        step = max(1, len(valid_ply_indices) // self.max_positions_per_game)
        sampled_plies = set(valid_ply_indices[::step][: self.max_positions_per_game])

        for ply_idx, played_move in enumerate(moves):
            if ply_idx in sampled_plies and not board.is_game_over():
                fen_before = board.fen()
                turn = board.turn  # True = White, False = Black

                # 1. Positive Example: The played master move (target = 1)
                examples.append(
                    {
                        "game_id": game_id,
                        "ply": ply_idx,
                        "fen": fen_before,
                        "turn": int(turn),
                        "move_uci": played_move.uci(),
                        "move_san": board.san(played_move),
                        "is_played_move": 1,
                        "is_quality_move": 1,  # Target label
                    }
                )

                # 2. Negative/Alternative Examples: Sampled unplayed legal candidate moves (target = 0)
                legal_moves = [m for m in board.legal_moves if m != played_move]
                if legal_moves:
                    # Deterministic candidate selection based on seed and ply
                    sampled_candidates = legal_moves[: self.candidate_alternatives_per_pos]
                    for cand in sampled_candidates:
                        examples.append(
                            {
                                "game_id": game_id,
                                "ply": ply_idx,
                                "fen": fen_before,
                                "turn": int(turn),
                                "move_uci": cand.uci(),
                                "move_san": board.san(cand),
                                "is_played_move": 0,
                                "is_quality_move": 0,  # Target label
                            }
                        )

            board.push(played_move)

        return examples

"""Production PGN Parser and Online Chess Platform Importer (Lichess & Chess.com).

Provides standard-compliant PGN extraction, metadata parsing, and remote API fetching
from public online chess profiles with robust error handling and rate-limit friendliness.
"""

from __future__ import annotations

import io
import json
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import chess
import chess.pgn


class PGNService:
    """Service to parse, validate, and fetch PGN games from text or online platforms."""

    @staticmethod
    def parse_pgn_text(pgn_text: str) -> Dict[str, Any]:
        """Parse raw PGN text into metadata headers and a clean sequence of moves.

        Returns a dictionary containing game headers, moves (SAN & UCI), and starting FEN.
        """
        pgn_io = io.StringIO(pgn_text.strip())
        game = chess.pgn.read_game(pgn_io)

        if game is None:
            raise ValueError("Invalid PGN text: Unable to parse game structure.")

        headers = {k: v for k, v in game.headers.items()}
        board = game.board()
        initial_fen = board.fen()

        moves_san: List[str] = []
        moves_uci: List[str] = []

        for move in game.mainline_moves():
            san = board.san(move)
            uci = move.uci()
            moves_san.append(san)
            moves_uci.append(uci)
            board.push(move)

        return {
            "headers": headers,
            "white": headers.get("White", "Unknown Player"),
            "black": headers.get("Black", "Unknown Player"),
            "white_elo": headers.get("WhiteElo", "Unrated"),
            "black_elo": headers.get("BlackElo", "Unrated"),
            "event": headers.get("Event", "Casual Game"),
            "date": headers.get("Date", "Unknown"),
            "result": headers.get("Result", "*"),
            "eco": headers.get("ECO", ""),
            "initial_fen": initial_fen,
            "final_fen": board.fen(),
            "moves_san": moves_san,
            "moves_uci": moves_uci,
            "ply_count": len(moves_san),
        }

    @staticmethod
    def fetch_lichess_games(username: str, max_games: int = 5) -> List[Dict[str, Any]]:
        """Fetch latest public games for a given Lichess username.

        Uses the official Lichess open API with ndjson format.
        """
        username = username.strip()
        url = (
            f"https://lichess.org/api/games/user/{username}"
            f"?max={max(1, min(max_games, 20))}&pgnInBody=true&clocks=false&evals=false"
        )

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ChessMindAI-Analytics/1.0 (Educational/Analysis Platform)",
                "Accept": "application/x-ndjson",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(f"Lichess user '{username}' was not found.")
            elif e.code == 429:
                raise ValueError("Lichess rate limit reached. Please wait a moment and try again.")
            raise ValueError(f"Lichess API returned HTTP error: {e.code}")
        except urllib.error.URLError as e:
            raise ValueError(f"Network error contacting Lichess: {e.reason}")

        parsed_games: List[Dict[str, Any]] = []
        # Each line is a separate JSON object or PGN block
        # With Accept: application/x-ndjson, lichess returns ndjson
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        for line in lines:
            try:
                data = json.loads(line)
                game_id = data.get("id", "")
                players = data.get("players", {})
                white_user = players.get("white", {}).get("user", {}).get("name", "White")
                white_rating = players.get("white", {}).get("rating", "Unrated")
                black_user = players.get("black", {}).get("user", {}).get("name", "Black")
                black_rating = players.get("black", {}).get("rating", "Unrated")
                winner = data.get("winner")
                status = data.get("status")

                if winner == "white":
                    result = "1-0"
                elif winner == "black":
                    result = "0-1"
                elif status == "draw":
                    result = "1/2-1/2"
                else:
                    result = "*"

                moves_str = data.get("moves", "")
                moves = moves_str.split() if moves_str else []

                # Convert UCI/SAN moves if necessary
                board = chess.Board()
                san_moves = []
                for m_str in moves:
                    try:
                        m = board.parse_san(m_str) if m_str in [board.san(l) for l in board.legal_moves] else chess.Move.from_uci(m_str)
                        san_moves.append(board.san(m))
                        board.push(m)
                    except Exception:
                        break

                parsed_games.append({
                    "id": game_id,
                    "platform": "lichess",
                    "white": white_user,
                    "black": black_user,
                    "white_elo": str(white_rating),
                    "black_elo": str(black_rating),
                    "result": result,
                    "speed": data.get("speed", "standard"),
                    "moves_san": san_moves,
                    "ply_count": len(san_moves),
                    "url": f"https://lichess.org/{game_id}",
                })
            except json.JSONDecodeError:
                continue

        return parsed_games

    @staticmethod
    def fetch_chesscom_games(username: str, max_games: int = 5) -> List[Dict[str, Any]]:
        """Fetch latest public games for a given Chess.com username.

        Uses the official public Chess.com Published Data API.
        """
        username = username.strip().lower()
        # 1. Fetch archives list
        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
        req = urllib.request.Request(
            archives_url,
            headers={
                "User-Agent": "ChessMindAI-Analytics/1.0 (contact: chessmind@example.com)",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                archives_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(f"Chess.com user '{username}' was not found.")
            raise ValueError(f"Chess.com API error: {e.code}")
        except urllib.error.URLError as e:
            raise ValueError(f"Network error contacting Chess.com: {e.reason}")

        archives = archives_data.get("archives", [])
        if not archives:
            return []

        # Get latest monthly archive
        latest_archive_url = archives[-1]
        req_latest = urllib.request.Request(
            latest_archive_url,
            headers={
                "User-Agent": "ChessMindAI-Analytics/1.0",
            },
        )

        with urllib.request.urlopen(req_latest, timeout=8) as response:
            monthly_data = json.loads(response.read().decode("utf-8"))

        raw_games = monthly_data.get("games", [])
        # Take most recent games
        recent_games = list(reversed(raw_games))[:max_games]

        parsed_games: List[Dict[str, Any]] = []
        for g in recent_games:
            pgn_str = g.get("pgn", "")
            if pgn_str:
                try:
                    parsed = PGNService.parse_pgn_text(pgn_str)
                    parsed["platform"] = "chesscom"
                    parsed["url"] = g.get("url", "")
                    parsed_games.append(parsed)
                except Exception:
                    continue

        return parsed_games


# Global singleton PGN service instance
pgn_service = PGNService()


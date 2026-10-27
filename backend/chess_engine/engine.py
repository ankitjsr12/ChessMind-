"""Chess Engine Core Module for ChessMind AI.

This module implements the complete chess game engine wrapping python-chess.
It provides strict rule validation, move execution, undoing, FEN/PGN import/export,
comprehensive state extraction, and feature representations for Stockfish,
Machine Learning, and Deep Learning modules.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import chess
import chess.pgn

from backend.chess_engine.exceptions import (
    GameOverError,
    IllegalMoveError,
    InvalidFENError,
    InvalidMoveError,
    InvalidPGNError,
    NoMovesToUndoError,
)
from backend.chess_engine.models import (
    BaseMovePredictor,
    BoardState,
    CastlingRights,
    GameResult,
    GameTermination,
    MoveRecord,
    MoveResult,
    PieceColor,
    PieceType,
    TerminationReason,
)


class ChessEngine:
    """Core chess game engine implementing standard chess rules, move tracking,

    state queries, PGN/FEN support, and ML feature representations.
    """

    STARTING_FEN = chess.STARTING_FEN

    # Piece symbols for White and Black
    PIECE_SYMBOLS = ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]

    def __init__(self, fen: Optional[str] = None) -> None:
        """Initialize a new chess engine instance.

        Args:
            fen: Optional FEN string. If None, the standard starting position is used.

        Raises:
            InvalidFENError: If the provided FEN is syntactically invalid or illegal.
        """
        self._initial_fen: str = fen if fen is not None else self.STARTING_FEN
        self._board: chess.Board = self._create_board(self._initial_fen)
        self._history: List[MoveRecord] = []
        self._draw_claimed: bool = False
        self._draw_claimed_reason: Optional[str] = None

    # -------------------------------------------------------------------------
    # Board Initialization & Reset
    # -------------------------------------------------------------------------

    @classmethod
    def is_valid_fen(cls, fen: str) -> bool:
        """Check whether a FEN string is syntactically and legally valid.

        Args:
            fen: The FEN string to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            board = chess.Board(fen)
            return board.is_valid()
        except (ValueError, IndexError):
            return False

    def _create_board(self, fen: str) -> chess.Board:
        """Instantiate and validate a chess.Board from FEN.

        Args:
            fen: FEN string to parse.

        Returns:
            A validated chess.Board instance.

        Raises:
            InvalidFENError: If FEN is invalid or illegal.
        """
        try:
            board = chess.Board(fen)
        except (ValueError, IndexError) as err:
            raise InvalidFENError(fen, reason=str(err)) from err

        if not board.is_valid():
            status = board.status()
            reasons = []
            if status & chess.STATUS_NO_WHITE_KING:
                reasons.append("Missing white king")
            if status & chess.STATUS_NO_BLACK_KING:
                reasons.append("Missing black king")
            if status & chess.STATUS_TOO_MANY_KINGS:
                reasons.append("Too many kings")
            if status & chess.STATUS_PAWNS_ON_BACKRANK:
                reasons.append("Pawns on first or eighth rank")
            if status & chess.STATUS_OPPOSITE_CHECK:
                reasons.append("Opposite king is currently in check")
            reason_str = ", ".join(reasons) if reasons else "Illegal piece placement"
            raise InvalidFENError(fen, reason=reason_str)

        return board

    def reset(self) -> None:
        """Reset the board to the standard initial chess position."""
        self._initial_fen = self.STARTING_FEN
        self._board = chess.Board(self.STARTING_FEN)
        self._history.clear()
        self._draw_claimed = False
        self._draw_claimed_reason = None

    def reset_to_fen(self, fen: str) -> None:
        """Reset the board to a custom position defined by a FEN string.

        Args:
            fen: The FEN string for the new starting position.

        Raises:
            InvalidFENError: If the FEN string is invalid or illegal.
        """
        self._board = self._create_board(fen)
        self._initial_fen = fen
        self._history.clear()
        self._draw_claimed = False
        self._draw_claimed_reason = None

    # -------------------------------------------------------------------------
    # Properties & Status Accessors
    # -------------------------------------------------------------------------

    @property
    def board(self) -> chess.Board:
        """Return a copy of the internal chess.Board instance."""
        return self._board.copy()

    @property
    def fen(self) -> str:
        """Return the current FEN string representation of the board."""
        return self._board.fen()

    @property
    def turn(self) -> PieceColor:
        """Return the color of the player whose turn it is to move."""
        return PieceColor.from_chess(self._board.turn)

    @property
    def fullmove_number(self) -> int:
        """Return the current fullmove number (starts at 1, incremented after Black moves)."""
        return self._board.fullmove_number

    @property
    def halfmove_clock(self) -> int:
        """Return the halfmove clock counting towards the 50-move rule."""
        return self._board.halfmove_clock

    def is_check(self) -> bool:
        """Check if the active player's king is currently in check."""
        return self._board.is_check()

    def is_checkmate(self) -> bool:
        """Check if the active player has been checkmated."""
        return self._board.is_checkmate()

    def is_stalemate(self) -> bool:
        """Check if the current position is stalemate (no legal moves and not in check)."""
        return self._board.is_stalemate()

    def is_insufficient_material(self) -> bool:
        """Check if neither side has sufficient material to force a checkmate."""
        return self._board.is_insufficient_material()

    def is_fivefold_repetition(self) -> bool:
        """Check if identical position has occurred five times (mandatory draw)."""
        return self._board.is_fivefold_repetition()

    def is_seventyfive_moves(self) -> bool:
        """Check if 75 moves have elapsed without pawn move or capture (mandatory draw)."""
        return self._board.is_seventyfive_moves()

    def can_claim_threefold_repetition(self) -> bool:
        """Check if current player can claim a draw by threefold repetition."""
        return self._board.can_claim_threefold_repetition()

    def can_claim_fifty_moves(self) -> bool:
        """Check if current player can claim a draw by 50-move rule."""
        return self._board.can_claim_fifty_moves()

    def can_claim_draw(self) -> bool:
        """Check if the active player can claim a draw by threefold repetition or 50 moves."""
        return self._board.can_claim_draw()

    def claim_draw(self) -> GameTermination:
        """Actively claim a draw by threefold repetition or 50-move rule if eligible.

        Returns:
            GameTermination indicating the drawn verdict.

        Raises:
            IllegalMoveError: If the current position does not satisfy draw claim criteria.
        """
        if not self.can_claim_draw():
            raise IllegalMoveError(
                move_str="claim_draw",
                fen=self.fen,
                reason="Draw cannot be claimed: neither threefold repetition nor 50-move rule satisfied",
            )
        self._draw_claimed = True
        self._draw_claimed_reason = (
            "threefold_repetition"
            if self.can_claim_threefold_repetition()
            else "fifty_moves"
        )
        return self.get_game_result()

    def is_draw(self) -> bool:
        """Check if the game has ended in any form of draw (automatic or claimable)."""
        return (
            self._draw_claimed
            or self.is_stalemate()
            or self.is_insufficient_material()
            or self.is_fivefold_repetition()
            or self.is_seventyfive_moves()
            or self.can_claim_draw()
        )

    def is_game_over(self, claim_draw: bool = False) -> bool:
        """Check if the game has terminated (checkmate, draw, or claimed draw).

        Args:
            claim_draw: If True, considers claimable draws (threefold/50-move) as game over.
        """
        if self._draw_claimed:
            return True
        return self._board.is_game_over(claim_draw=claim_draw)

    # -------------------------------------------------------------------------
    # Move Validation & Parsing
    # -------------------------------------------------------------------------

    def parse_move(self, move_input: Union[str, chess.Move]) -> chess.Move:
        """Parse and validate a move in UCI, SAN, or chess.Move format.

        Args:
            move_input: The move representation (e.g. 'e2e4', 'e4', 'Nf3', or chess.Move).

        Returns:
            The validated legal chess.Move object.

        Raises:
            InvalidMoveError: If the move string syntax is invalid or unparseable.
            IllegalMoveError: If the move is recognized but illegal in the current position.
        """
        if isinstance(move_input, chess.Move):
            if move_input not in self._board.legal_moves:
                raise IllegalMoveError(
                    move_str=move_input.uci(),
                    fen=self._board.fen(),
                    reason=f"Move '{move_input.uci()}' is illegal in current position",
                )
            return move_input

        if not isinstance(move_input, str):
            raise InvalidMoveError(str(move_input), "Move input must be a string or chess.Move")

        move_str = move_input.strip()
        if not move_str:
            raise InvalidMoveError(move_str, "Move string cannot be empty")

        # 1. Try UCI parsing first
        try:
            candidate = chess.Move.from_uci(move_str)
            if candidate in self._board.legal_moves:
                return candidate
            # Valid UCI format, but illegal in current position
            raise IllegalMoveError(
                move_str=move_str,
                fen=self._board.fen(),
                reason=f"UCI move '{move_str}' violates rules for current position",
            )
        except chess.InvalidMoveError:
            # Not valid UCI, will attempt SAN parsing next
            pass

        # 2. Try SAN parsing
        try:
            candidate = self._board.parse_san(move_str)
            if candidate in self._board.legal_moves:
                return candidate
        except chess.IllegalMoveError as err:
            raise IllegalMoveError(
                move_str=move_str,
                fen=self._board.fen(),
                reason=f"SAN move '{move_str}' is illegal: {err}",
            ) from err
        except chess.AmbiguousMoveError as err:
            raise IllegalMoveError(
                move_str=move_str,
                fen=self._board.fen(),
                reason=f"SAN move '{move_str}' is ambiguous: {err}",
            ) from err
        except chess.InvalidMoveError as err:
            raise InvalidMoveError(
                move_str=move_str,
                reason=f"Invalid move syntax '{move_str}': {err}",
            ) from err

        # Fallback if unhandled
        raise InvalidMoveError(move_str, "Could not interpret move as legal UCI or SAN")

    def is_legal_move(self, move_input: Union[str, chess.Move]) -> bool:
        """Check if a move is legal without raising an exception.

        Args:
            move_input: UCI string, SAN string, or chess.Move.

        Returns:
            True if legal, False otherwise.
        """
        try:
            self.parse_move(move_input)
            return True
        except (InvalidMoveError, IllegalMoveError):
            return False

    def get_legal_moves(self, format: str = "uci") -> List[str]:
        """Retrieve all legal moves in the current position.

        Args:
            format: 'uci' for UCI strings, 'san' for standard algebraic notation.

        Returns:
            List of legal move strings.

        Raises:
            ValueError: If format is not 'uci' or 'san'.
        """
        fmt = format.lower()
        if fmt == "uci":
            return [move.uci() for move in self._board.legal_moves]
        if fmt == "san":
            return [self._board.san(move) for move in self._board.legal_moves]
        raise ValueError(f"Unsupported format '{format}'. Use 'uci' or 'san'.")

    def get_legal_moves_uci(self) -> List[str]:
        """Shortcut to get all legal moves in UCI format."""
        return self.get_legal_moves(format="uci")

    def get_legal_moves_san(self) -> List[str]:
        """Shortcut to get all legal moves in SAN format."""
        return self.get_legal_moves(format="san")

    # -------------------------------------------------------------------------
    # Move Execution & Undo
    # -------------------------------------------------------------------------

    def make_move(self, move_input: Union[str, chess.Move]) -> MoveResult:
        """Execute a move on the board and update game history.

        Args:
            move_input: UCI string (e.g. 'e2e4'), SAN string (e.g. 'e4'), or chess.Move.

        Returns:
            A MoveResult containing the MoveRecord, BoardState, and GameTermination.

        Raises:
            GameOverError: If the game has already concluded.
            InvalidMoveError: If the move format is invalid.
            IllegalMoveError: If the move violates chess rules.
        """
        if self.is_game_over(claim_draw=False) or self._draw_claimed:
            term = self.get_game_result()
            raise GameOverError(result=term.result_code.value, reason=term.reason.value)

        move = self.parse_move(move_input)

        # Pre-move metadata extraction
        san = self._board.san(move)
        uci = move.uci()
        fen_before = self._board.fen()
        turn = self.turn
        fullmove = self._board.fullmove_number

        piece_at_from = self._board.piece_at(move.from_square)
        piece_moved = piece_at_from.symbol() if piece_at_from else ""

        is_capture = self._board.is_capture(move)
        is_castling = self._board.is_castling(move)
        is_en_passant = self._board.is_en_passant(move)
        is_promotion = move.promotion is not None
        promotion_piece = (
            chess.piece_symbol(move.promotion).upper() if move.promotion else None
        )

        captured_piece: Optional[str] = None
        if is_en_passant:
            captured_piece = "p" if turn == PieceColor.WHITE else "P"
        elif is_capture:
            target = self._board.piece_at(move.to_square)
            captured_piece = target.symbol() if target else None

        # Execute move on board
        self._board.push(move)

        fen_after = self._board.fen()
        is_check = self._board.is_check()
        is_checkmate = self._board.is_checkmate()

        record = MoveRecord(
            move_number=fullmove,
            uci=uci,
            san=san,
            turn=turn,
            fen_before=fen_before,
            fen_after=fen_after,
            piece_moved=piece_moved,
            captured_piece=captured_piece,
            is_capture=is_capture,
            is_check=is_check,
            is_checkmate=is_checkmate,
            is_castling=is_castling,
            is_en_passant=is_en_passant,
            is_promotion=is_promotion,
            promotion_piece=promotion_piece,
        )
        self._history.append(record)

        board_state = self.get_board_state()
        termination = self.get_game_result()

        return MoveResult(
            move_record=record,
            board_state=board_state,
            termination=termination,
        )

    def undo_move(self) -> MoveRecord:
        """Undo the last played move and revert the board state.

        Returns:
            The MoveRecord of the undone move.

        Raises:
            NoMovesToUndoError: If there are no moves to undo in history.
        """
        if not self._history or len(self._board.move_stack) == 0:
            raise NoMovesToUndoError()

        self._board.pop()
        self._draw_claimed = False
        self._draw_claimed_reason = None
        return self._history.pop()

    def undo_moves(self, count: int) -> List[MoveRecord]:
        """Undo multiple moves sequentially.

        Args:
            count: Number of moves to undo.

        Returns:
            List of undone MoveRecords in reverse chronological order.

        Raises:
            ValueError: If count is less than 1.
            NoMovesToUndoError: If count exceeds available moves in history.
        """
        if count < 1:
            raise ValueError(f"Count must be at least 1, got {count}")
        if count > len(self._history):
            raise NoMovesToUndoError(
                f"Cannot undo {count} moves; only {len(self._history)} moves in history"
            )

        undone: List[MoveRecord] = []
        for _ in range(count):
            undone.append(self.undo_move())
        return undone

    # -------------------------------------------------------------------------
    # History & Game Inspection
    # -------------------------------------------------------------------------

    def get_move_history(self) -> List[MoveRecord]:
        """Return a copy of the full move history records."""
        return list(self._history)

    def get_uci_history(self) -> List[str]:
        """Return a list of all executed moves in UCI notation."""
        return [record.uci for record in self._history]

    def get_san_history(self) -> List[str]:
        """Return a list of all executed moves in SAN notation."""
        return [record.san for record in self._history]

    def get_captured_pieces(self) -> Dict[str, List[str]]:
        """Return the pieces captured so far grouped by the player who lost them.

        Returns:
            Dictionary with 'white' (white pieces captured) and 'black' (black pieces captured).
        """
        white_captured: List[str] = []
        black_captured: List[str] = []

        for record in self._history:
            if record.captured_piece:
                if record.captured_piece.isupper():
                    white_captured.append(record.captured_piece)
                else:
                    black_captured.append(record.captured_piece)

        return {"white": white_captured, "black": black_captured}

    # -------------------------------------------------------------------------
    # Game Termination & Verdicts
    # -------------------------------------------------------------------------

    def get_game_result(self, claim_draw: bool = False) -> GameTermination:
        """Determine and return the game's termination state and result.

        Args:
            claim_draw: If True, treats claimable draws (threefold repetition or
                50-move rule) as game termination even if not explicitly claimed.

        Returns:
            GameTermination containing result code, winner, reason, and description.
        """
        if self._draw_claimed:
            reason = (
                TerminationReason.THREEFOLD_REPETITION
                if self._draw_claimed_reason == "threefold_repetition"
                else TerminationReason.FIFTY_MOVES
            )
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=reason,
                description=f"Draw claimed by {reason.value}",
            )

        if self._board.is_checkmate():
            # The player whose turn it is has no legal moves and is in check: loser is current turn
            winner = PieceColor.BLACK if self._board.turn == chess.WHITE else PieceColor.WHITE
            result_code = GameResult.BLACK_WINS if winner == PieceColor.BLACK else GameResult.WHITE_WINS
            return GameTermination(
                is_terminated=True,
                winner=winner,
                result_code=result_code,
                reason=TerminationReason.CHECKMATE,
                description=f"Checkmate: {winner.value.capitalize()} wins",
            )

        if self._board.is_stalemate():
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=TerminationReason.STALEMATE,
                description="Draw by stalemate",
            )

        if self._board.is_insufficient_material():
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=TerminationReason.INSUFFICIENT_MATERIAL,
                description="Draw by insufficient material",
            )

        if self._board.is_seventyfive_moves():
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=TerminationReason.SEVENTYFIVE_MOVES,
                description="Draw by 75-move rule",
            )

        if self._board.is_fivefold_repetition():
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=TerminationReason.FIVEFOLD_REPETITION,
                description="Draw by fivefold repetition",
            )

        if claim_draw and self._board.can_claim_threefold_repetition():
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=TerminationReason.THREEFOLD_REPETITION,
                description="Draw by threefold repetition claim",
            )

        if claim_draw and self._board.can_claim_fifty_moves():
            return GameTermination(
                is_terminated=True,
                winner=None,
                result_code=GameResult.DRAW,
                reason=TerminationReason.FIFTY_MOVES,
                description="Draw by 50-move rule claim",
            )

        return GameTermination(
            is_terminated=False,
            winner=None,
            result_code=GameResult.IN_PROGRESS,
            reason=TerminationReason.NOT_TERMINATED,
            description="Game in progress",
        )

    # -------------------------------------------------------------------------
    # Board State Extraction
    # -------------------------------------------------------------------------

    def get_castling_rights(self) -> CastlingRights:
        """Return the current castling availability for both sides."""
        return CastlingRights(
            white_kingside=self._board.has_kingside_castling_rights(chess.WHITE),
            white_queenside=self._board.has_queenside_castling_rights(chess.WHITE),
            black_kingside=self._board.has_kingside_castling_rights(chess.BLACK),
            black_queenside=self._board.has_queenside_castling_rights(chess.BLACK),
        )

    def get_board_matrix(self) -> List[List[Optional[str]]]:
        """Return an 8x8 matrix of piece symbols.

        Row 0 represents Rank 8, Row 7 represents Rank 1.
        Col 0 represents File a, Col 7 represents File h.
        Empty squares are None.
        """
        matrix: List[List[Optional[str]]] = []
        for rank in range(7, -1, -1):
            row: List[Optional[str]] = []
            for file in range(8):
                square = chess.square(file, rank)
                piece = self._board.piece_at(square)
                row.append(piece.symbol() if piece else None)
            matrix.append(row)
        return matrix

    def get_piece_counts(self) -> Dict[str, int]:
        """Count the occurrences of each piece type currently on the board."""
        counts = {symbol: 0 for symbol in self.PIECE_SYMBOLS}
        for square in chess.SQUARES:
            piece = self._board.piece_at(square)
            if piece:
                counts[piece.symbol()] += 1
        return counts

    def get_board_state(self) -> BoardState:
        """Construct a comprehensive BoardState snapshot."""
        term = self.get_game_result()
        draw_reason = term.description if term.is_terminated and term.winner is None else None

        ep_square = (
            chess.square_name(self._board.ep_square)
            if self._board.ep_square is not None
            else None
        )

        return BoardState(
            fen=self.fen,
            turn=self.turn,
            fullmove_number=self.fullmove_number,
            halfmove_clock=self.halfmove_clock,
            is_check=self.is_check(),
            is_checkmate=self.is_checkmate(),
            is_stalemate=self.is_stalemate(),
            is_insufficient_material=self.is_insufficient_material(),
            is_fivefold_repetition=self.is_fivefold_repetition(),
            is_seventyfive_moves=self.is_seventyfive_moves(),
            can_claim_draw=self.can_claim_draw(),
            can_claim_threefold_repetition=self.can_claim_threefold_repetition(),
            can_claim_fifty_moves=self.can_claim_fifty_moves(),
            is_game_over=term.is_terminated,
            draw_reason=draw_reason,
            legal_moves_uci=self.get_legal_moves_uci(),
            legal_moves_san=self.get_legal_moves_san(),
            castling_rights=self.get_castling_rights(),
            en_passant_square=ep_square,
            board_matrix=self.get_board_matrix(),
            piece_counts=self.get_piece_counts(),
            captured_pieces=self.get_captured_pieces(),
        )

    # -------------------------------------------------------------------------
    # PGN Import / Export
    # -------------------------------------------------------------------------

    def export_pgn(self, headers: Optional[Dict[str, str]] = None) -> str:
        """Export the current game history to standard PGN notation.

        Args:
            headers: Optional dictionary of PGN headers (e.g. Event, White, Black).

        Returns:
            PGN formatted string representing the game.
        """
        game = chess.pgn.Game.from_board(self._board)

        # Apply default headers
        game.headers["Event"] = "ChessMind AI Match"
        game.headers["Site"] = "ChessMind Engine"
        game.headers["Date"] = "????.??.??"
        game.headers["Round"] = "1"
        game.headers["White"] = "White Player"
        game.headers["Black"] = "Black Player"
        game.headers["Result"] = self.get_game_result().result_code.value

        # Override with custom headers if provided
        if headers:
            for key, val in headers.items():
                game.headers[key] = str(val)

        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        return game.accept(exporter)

    def import_pgn(self, pgn_str: str) -> None:
        """Import a game from a PGN formatted string.

        Replays the moves sequentially while reconstructing the move history.

        Args:
            pgn_str: String containing the PGN game text.

        Raises:
            InvalidPGNError: If the PGN string cannot be parsed or contains illegal moves.
        """
        if not pgn_str or not pgn_str.strip():
            raise InvalidPGNError(pgn_str, reason="PGN string cannot be empty")

        pgn_io = io.StringIO(pgn_str.strip())
        try:
            game = chess.pgn.read_game(pgn_io)
        except Exception as err:
            raise InvalidPGNError(pgn_str, reason=str(err)) from err

        if game is None:
            raise InvalidPGNError(pgn_str, reason="No valid chess game found in PGN string")

        if game.errors:
            error_details = "; ".join(str(e) for e in game.errors)
            raise InvalidPGNError(pgn_str, reason=f"PGN syntax error: {error_details}")

        # Validate that unparseable tokens were not silently ignored in the movetext body
        body_lines = [l for l in pgn_str.splitlines() if not l.strip().startswith("[")]
        body = " ".join(body_lines)
        body = re.sub(r"\{[^}]*\}", "", body)  # Strip {} comments
        body = re.sub(r";[^\n]*", "", body)    # Strip ; comments
        raw_tokens = [t for t in re.split(r"\s+", body.strip()) if t]
        move_tokens = [
            t for t in raw_tokens
            if not re.match(r"^\d+(\.+)?$", t)
            and t not in ["1-0", "0-1", "1/2-1/2", "*"]
            and not re.match(r"^\$\d+$", t)
            and not re.match(r"^[!?]+$", t)
        ]
        parsed_moves = list(game.mainline_moves())
        if len(move_tokens) != len(parsed_moves):
            unparsed = move_tokens[len(parsed_moves):]
            raise InvalidPGNError(
                pgn_str,
                reason=f"Unrecognized or invalid move tokens in PGN movetext: {unparsed}",
            )

        # Initialize from starting position of PGN
        try:
            root_board = game.board()
            self._board = root_board
            self._initial_fen = root_board.fen()
            self._history.clear()
            self._draw_claimed = False
            self._draw_claimed_reason = None
        except Exception as err:
            raise InvalidPGNError(pgn_str, reason=f"Failed to initialize board from PGN: {err}") from err

        # Replay each move safely
        for move in game.mainline_moves():
            if move not in self._board.legal_moves:
                raise InvalidPGNError(
                    pgn_str,
                    reason=f"Illegal move '{move.uci()}' encountered in PGN at FEN {self._board.fen()}",
                )
            self.make_move(move)

    # -------------------------------------------------------------------------
    # AI / ML / Deep Learning Integration Features
    # -------------------------------------------------------------------------

    def get_stockfish_position_command(self) -> str:
        """Generate the UCI protocol position command for Stockfish.

        Returns:
            A string formatted for UCI protocol (e.g. 'position startpos moves e2e4 e7e5').
        """
        moves_part = " ".join(self.get_uci_history())
        if self._initial_fen == self.STARTING_FEN:
            base = "position startpos"
        else:
            base = f"position fen {self._initial_fen}"

        return f"{base} moves {moves_part}".strip() if moves_part else base

    def get_bitboard_planes(self) -> Dict[str, int]:
        """Extract 64-bit unsigned integer bitboards for all 12 piece types.

        Useful for high-speed classical evaluators, bitboard engines, and feature vectors.

        Returns:
            Dict mapping piece symbol ('P', 'N', ..., 'k') to its 64-bit integer bitmask.
        """
        planes: Dict[str, int] = {}
        for piece_type in chess.PIECE_TYPES:
            for color in [chess.WHITE, chess.BLACK]:
                symbol = chess.piece_symbol(piece_type).upper() if color == chess.WHITE else chess.piece_symbol(piece_type).lower()
                mask = self._board.pieces_mask(piece_type, color)
                planes[symbol] = mask
        return planes

    def get_tensor_representation(self) -> List[List[List[float]]]:
        """Generate a 14-channel 8x8 spatial tensor representation for Deep Learning models.

        Channels (each an 8x8 matrix corresponding to ranks 8..1 and files a..h):
            0..5: White pieces (Pawn, Knight, Bishop, Rook, Queen, King)
            6..11: Black pieces (pawn, knight, bishop, rook, queen, king)
            12: Turn indicator (1.0 for White, 0.0 for Black)
            13: Castling rights (White kingside=0.25, queenside=0.25, Black kingside=0.25, queenside=0.25)

        Returns:
            A 3D list with shape (14, 8, 8) readily convertible to torch.Tensor or numpy.ndarray.
        """
        # 14 channels of 8x8
        tensor: List[List[List[float]]] = [[[0.0 for _ in range(8)] for _ in range(8)] for _ in range(14)]

        piece_channel_map = {
            ("P", chess.WHITE): 0,
            ("N", chess.WHITE): 1,
            ("B", chess.WHITE): 2,
            ("R", chess.WHITE): 3,
            ("Q", chess.WHITE): 4,
            ("K", chess.WHITE): 5,
            ("p", chess.BLACK): 6,
            ("n", chess.BLACK): 7,
            ("b", chess.BLACK): 8,
            ("r", chess.BLACK): 9,
            ("q", chess.BLACK): 10,
            ("k", chess.BLACK): 11,
        }

        # Populate piece channels
        for rank in range(8):
            for file in range(8):
                square = chess.square(file, rank)
                piece = self._board.piece_at(square)
                if piece:
                    symbol = piece.symbol()
                    channel = piece_channel_map[(symbol, piece.color)]
                    # In 8x8 image coordinates, rank 7 is top (row 0), rank 0 is bottom (row 7)
                    row = 7 - rank
                    col = file
                    tensor[channel][row][col] = 1.0

        # Channel 12: Turn
        turn_val = 1.0 if self._board.turn == chess.WHITE else 0.0
        for r in range(8):
            for c in range(8):
                tensor[12][r][c] = turn_val

        # Channel 13: Castling rights
        castling_val = 0.0
        if self._board.has_kingside_castling_rights(chess.WHITE):
            castling_val += 0.25
        if self._board.has_queenside_castling_rights(chess.WHITE):
            castling_val += 0.25
        if self._board.has_kingside_castling_rights(chess.BLACK):
            castling_val += 0.25
        if self._board.has_queenside_castling_rights(chess.BLACK):
            castling_val += 0.25

        for r in range(8):
            for c in range(8):
                tensor[13][r][c] = castling_val

        return tensor

    def play_ai_move(self, predictor: BaseMovePredictor) -> MoveResult:
        """Allow an AI opponent (Stockfish, ML, or DL model) to choose and execute a move.

        Args:
            predictor: Any predictor object conforming to the BaseMovePredictor protocol.

        Returns:
            MoveResult following execution of the AI's move.

        Raises:
            GameOverError: If the game is already finished.
            IllegalMoveError: If the predictor suggested an illegal move.
            InvalidMoveError: If the predictor returned an unparseable move.
            ValueError: If the predictor returns None or fails to find a move.
        """
        if self.is_game_over(claim_draw=True):
            term = self.get_game_result()
            raise GameOverError(result=term.result_code.value, reason=term.reason.value)

        legal_moves = self.get_legal_moves_uci()
        if not legal_moves:
            term = self.get_game_result()
            raise GameOverError(result=term.result_code.value, reason=term.reason.value)

        predicted_move = predictor.predict_move(self.fen, legal_moves)
        if not predicted_move:
            raise ValueError(f"AI predictor {predictor} returned no move from position {self.fen}")

        return self.make_move(predicted_move)

    # -------------------------------------------------------------------------
    # Visualization / String Representation
    # -------------------------------------------------------------------------

    def render_ascii(self) -> str:
        """Render a clean ASCII chessboard representation."""
        return str(self._board)

    def __repr__(self) -> str:
        return f"ChessEngine(fen='{self.fen}', moves_count={len(self._history)})"

    def __str__(self) -> str:
        return self.render_ascii()

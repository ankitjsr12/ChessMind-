"""FastAPI Backend Service for ChessMind AI Analytics Dashboard."""

from datetime import datetime, timezone
import json
import math
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
import chess
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.schemas import (
    CandidatesRequest,
    ChessComImportRequest,
    CreateRoomRequest,
    GameReviewRequest,
    JoinRoomRequest,
    LichessImportRequest,
    ModelComparisonRequest,
    MoveRequest,
    OpeningExplorerRequest,
    PGNReviewRequest,
    PlayAIRequest,
    PositionRequest,
    RoomActionRequest,
    RoomMoveRequest,
)
from backend.chess_engine import (
    ChessEngine,
    IllegalMoveError,
    InvalidFENError,
    blunder_detector,
    opening_book,
    pgn_service,
)
from backend.chess_engine.models import PieceColor
from backend.deep_learning import NeuralPositionEvaluator
from backend.ml import MLMoveQualityPredictor
from backend.online_rooms import (
    ColorPreference,
    OnlineRoom,
    PlayerConnectionState,
    RoomStatus,
    room_manager,
)
from backend.opponent_prediction import OpponentSearchEngine, PositionEvaluator
from backend.predictor import MoveRanker

app = FastAPI(
    title="ChessMind AI Backend API",
    description="Full-stack AI Chess Analysis API powering the Analytics Dashboard",
    version="1.0.0",
)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines with lazy or eager loaders
ranker = MoveRanker()
opponent_engine = OpponentSearchEngine(default_depth=3, default_time_limit=1.5)
ml_predictor = MLMoveQualityPredictor(autoload=True)
neural_evaluator = NeuralPositionEvaluator(autoload=True)


class RoomWebSocketManager:
    """Thread-safe WebSocket connection broker for online multiplayer rooms."""

    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = {}
        self._lock = threading.Lock()

    async def connect(self, room_code: str, websocket: WebSocket) -> None:
        await websocket.accept()
        code = room_code.upper().strip()
        with self._lock:
            if code not in self._connections:
                self._connections[code] = []
            self._connections[code].append(websocket)

    def disconnect(self, room_code: str, websocket: WebSocket) -> None:
        code = room_code.upper().strip()
        with self._lock:
            if code in self._connections:
                if websocket in self._connections[code]:
                    self._connections[code].remove(websocket)
                if not self._connections[code]:
                    del self._connections[code]

    async def broadcast_to_room(self, room_code: str, message: Dict[str, Any]) -> None:
        code = room_code.upper().strip()
        with self._lock:
            conns = list(self._connections.get(code, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                pass


ws_room_manager = RoomWebSocketManager()


@app.get("/")
def root_endpoint() -> Dict[str, Any]:
    """Service metadata and health summary."""
    return {
        "service": "ChessMind AI Backend API",
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }


@app.get("/health")
def root_health_check() -> Dict[str, Any]:
    """Alias for /api/health to support standard health probes."""
    return health_check()


@app.websocket("/ws")
async def websocket_general_endpoint(websocket: WebSocket) -> None:
    """General WebSocket connection endpoint for ping/pong and connection testing."""
    await websocket.accept()
    try:
        await websocket.send_json({
            "type": "connected",
            "service": "ChessMind AI WebSocket Gateway",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                action = payload.get("action", "ping")
            except Exception:
                action = data.strip().lower()

            if action == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif action == "health":
                await websocket.send_json({
                    "type": "health",
                    "data": health_check(),
                })
            else:
                await websocket.send_json({
                    "type": "ack",
                    "received": data,
                })
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/rooms/{room_code}")
async def websocket_room_endpoint(websocket: WebSocket, room_code: str) -> None:
    """WebSocket endpoint for real-time 1v1 online chess room synchronization."""
    code = room_code.upper().strip()
    room = room_manager.get_room(code)
    if not room:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "detail": f"Room '{code}' not found.",
        })
        await websocket.close(code=4004)
        return

    await ws_room_manager.connect(code, websocket)
    try:
        await websocket.send_json({
            "type": "room_state",
            "room_code": code,
            "room": room.to_dict(),
        })

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                msg = {"action": data.strip()}

            action = msg.get("action", "").lower()
            if action == "ping":
                await websocket.send_json({"type": "pong", "room_code": code})
            elif action == "sync":
                room.check_timeouts()
                await websocket.send_json({
                    "type": "room_state",
                    "room_code": code,
                    "room": room.to_dict(),
                })
            elif action == "move":
                user_id = msg.get("user_id")
                move_str = msg.get("move")
                if user_id and move_str:
                    try:
                        res = room.make_authoritative_move(user_id=user_id, move_str=move_str)
                        broadcast_data = {
                            "type": "move_played",
                            "room_code": code,
                            "played_move": res.move_record.san,
                            "fen": room.engine.fen,
                            "turn": room.engine.turn.value,
                            "is_check": res.move_record.is_check,
                            "is_game_over": room.status == RoomStatus.COMPLETED,
                            "room": room.to_dict(),
                        }
                        await ws_room_manager.broadcast_to_room(code, broadcast_data)
                    except Exception as err:
                        await websocket.send_json({"type": "error", "detail": str(err)})
    except WebSocketDisconnect:
        ws_room_manager.disconnect(code, websocket)


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Health check reporting backend module readiness."""
    stockfish_avail = False
    try:
        stockfish_avail = bool(ranker.stockfish.is_available())
    except Exception:
        stockfish_avail = False

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": {
            "chess_engine": True,
            "minimax_predictor": True,
            "stockfish": stockfish_avail,
            "opponent_search": True,
            "ml_model_trained": ml_predictor.is_trained,
            "neural_model_trained": neural_evaluator.is_trained,
            "online_rooms": True,
        },
        "active_rooms": room_manager.active_rooms_count(),
        "device": str(neural_evaluator.device) if neural_evaluator.is_trained else "cpu",
    }


@app.get("/api/dashboard/stats")
def get_dashboard_stats() -> Dict[str, Any]:
    """Provide summary statistics, move-quality distributions, and recent games."""
    return {
        "summary": {
            "total_games": 142,
            "wins": 78,
            "losses": 45,
            "draws": 19,
            "win_rate": 54.9,
            "average_accuracy": 82.4,
        },
        "move_quality_distribution": [
            {"tier": "Excellent", "count": 624, "percentage": 48.5, "color": "#10b981"},
            {"tier": "Good", "count": 382, "percentage": 29.7, "color": "#3b82f6"},
            {"tier": "Inaccuracy", "count": 148, "percentage": 11.5, "color": "#f59e0b"},
            {"tier": "Mistake", "count": 89, "percentage": 6.9, "color": "#f97316"},
            {"tier": "Blunder", "count": 44, "percentage": 3.4, "color": "#ef4444"},
        ],
        "accuracy_trends": [
            {"game": "Game 1", "accuracy": 74.2, "opponent": "1650 Bot"},
            {"game": "Game 2", "accuracy": 81.0, "opponent": "1750 Bot"},
            {"game": "Game 3", "accuracy": 79.5, "opponent": "1800 Bot"},
            {"game": "Game 4", "accuracy": 85.3, "opponent": "Human 1820"},
            {"game": "Game 5", "accuracy": 88.1, "opponent": "Master 2100"},
            {"game": "Game 6", "accuracy": 83.4, "opponent": "ChessMind AI"},
        ],
        "recent_games": [
            {"id": "g-101", "date": "2026-10-27", "white": "Player", "black": "ChessMind AI", "result": "1-0", "accuracy": 88.4, "moves": 34, "opening": "Ruy Lopez"},
            {"id": "g-102", "date": "2026-10-26", "white": "1900 Bot", "black": "Player", "result": "0-1", "accuracy": 85.1, "moves": 42, "opening": "Sicilian Defense"},
            {"id": "g-103", "date": "2026-10-26", "white": "Player", "black": "Stockfish L4", "result": "1/2-1/2", "accuracy": 81.6, "moves": 58, "opening": "Queen's Gambit"},
            {"id": "g-104", "date": "2026-10-25", "white": "Human 1780", "black": "Player", "result": "0-1", "accuracy": 79.2, "moves": 27, "opening": "French Defense"},
        ],
    }


@app.post("/api/engine/state")
def get_engine_state(req: PositionRequest) -> Dict[str, Any]:
    """Inspect chess board state and return legal moves."""
    try:
        engine = ChessEngine(req.fen)
        board = engine.board

        legal_moves = [
            {"uci": m.uci(), "san": board.san(m), "from": chess.square_name(m.from_square), "to": chess.square_name(m.to_square)}
            for m in board.legal_moves
        ]

        return {
            "fen": engine.fen,
            "turn": engine.turn.value,
            "is_check": engine.is_check(),
            "is_checkmate": engine.is_checkmate(),
            "is_stalemate": engine.is_stalemate(),
            "is_game_over": engine.is_game_over(),
            "fullmove_number": board.fullmove_number,
            "halfmove_clock": board.halfmove_clock,
            "legal_moves": legal_moves,
            "legal_moves_count": len(legal_moves),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/engine/play-move")
def play_move(req: MoveRequest) -> Dict[str, Any]:
    """Execute a move on the board and return resulting state."""
    try:
        engine = ChessEngine(req.fen)
        res = engine.make_move(req.move)
        move = res.move_record
        board = engine.board

        legal_moves = [
            {"uci": m.uci(), "san": board.san(m), "from": chess.square_name(m.from_square), "to": chess.square_name(m.to_square)}
            for m in board.legal_moves
        ]

        return {
            "fen": engine.fen,
            "played_move_uci": move.uci,
            "played_move_san": move.san,
            "turn": engine.turn.value,
            "is_check": engine.is_check(),
            "is_game_over": engine.is_game_over(),
            "legal_moves": legal_moves,
        }
    except IllegalMoveError as e:
        raise HTTPException(status_code=422, detail=f"Illegal move: {e.move_str}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/engine/play-ai")
def play_ai_move(req: PlayAIRequest) -> Dict[str, Any]:
    """Calculate and execute an AI response based on chosen difficulty."""
    try:
        engine = ChessEngine(req.fen)
        if engine.is_game_over():
            raise HTTPException(status_code=400, detail="Game is already over")

        t_start = time.perf_counter()
        ai_move_str = None

        if req.difficulty == "easy":
            # Shallow Minimax (depth 1)
            res = ranker.minimax.analyze(fen=engine.fen, depth=1)
            ai_move_str = res.best_move_uci if res.best_move_uci else list(engine.board.legal_moves)[0].uci()
        elif req.difficulty == "medium":
            # Minimax Alpha-Beta depth 3
            res = ranker.predict_best_moves(engine.fen, candidate_count=3, depth=3)
            ai_move_str = res.best_move_uci
        elif req.difficulty == "neural" and neural_evaluator.is_trained:
            # Neural candidate simulation
            ranked = neural_evaluator.evaluate_candidate_moves(engine.fen)
            ai_move_str = ranked[0]["move_uci"] if ranked else list(engine.board.legal_moves)[0].uci()
        else:
            # Master / Standard Predictor (Stockfish or Minimax fallback)
            res = ranker.predict_best_moves(engine.fen, candidate_count=3)
            ai_move_str = res.best_move_uci

        move_res = engine.make_move(ai_move_str)
        move_record = move_res.move_record
        dur_ms = (time.perf_counter() - t_start) * 1000

        return {
            "fen": engine.fen,
            "move": move_record.uci,
            "ai_move_uci": move_record.uci,
            "ai_move_san": move_record.san,
            "latency_ms": round(dur_ms, 1),
            "turn": engine.turn.value,
            "is_check": engine.is_check(),
            "is_game_over": engine.is_game_over(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/predict/best-move")
def predict_best_move(req: PositionRequest) -> Dict[str, Any]:
    """Module 2: Return best move, top 3 candidate alternatives, evaluation, and PV."""
    try:
        res = ranker.predict_best_moves(req.fen, candidate_count=4)
        return res.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/predict/opponent-response")
def predict_opponent_response(req: CandidatesRequest) -> Dict[str, Any]:
    """Module 3: Predict adversarial opponent replies and tactical consequences."""
    try:
        report = opponent_engine.analyze_candidate_consequences(
            fen_or_engine=req.fen,
            candidate_moves=req.candidate_moves,
            depth=3,
        )
        return report.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/predict/candidate-quality")
def predict_candidate_quality(req: CandidatesRequest) -> Dict[str, Any]:
    """Module 4: Machine Learning candidate move quality prediction."""
    try:
        if not ml_predictor.is_trained:
            raise HTTPException(status_code=503, detail="ML Model not trained yet. Run train_pipeline first.")
        report = ml_predictor.predict_move_quality(req.fen, candidate_moves=req.candidate_moves)
        return report.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/predict/neural-eval")
def predict_neural_evaluation(req: CandidatesRequest) -> Dict[str, Any]:
    """Module 5: Neural position evaluation and candidate ranking."""
    try:
        if not neural_evaluator.is_trained:
            raise HTTPException(status_code=503, detail="Neural model weights not trained yet.")
        pos_eval = neural_evaluator.evaluate_position(req.fen)
        candidates_ranked = neural_evaluator.evaluate_candidate_moves(req.fen, candidate_moves=req.candidate_moves)

        return {
            "position_evaluation": pos_eval,
            "candidate_rankings": candidates_ranked,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/review/game")
def review_game(req: GameReviewRequest) -> Dict[str, Any]:
    """Module 7: Move-by-move game accuracy review, ECO opening identification, and tactical blunder detection."""
    try:
        board = chess.Board(req.initial_fen or chess.STARTING_FEN)
        move_reviews: List[Dict[str, Any]] = []

        white_accuracies: List[float] = []
        black_accuracies: List[float] = []

        for ply_idx, move_str in enumerate(req.moves):
            turn_color = board.turn
            move = board.parse_san(move_str) if move_str in [board.san(m) for m in board.legal_moves] else chess.Move.from_uci(move_str)

            board_before = board.copy()

            # 1. Best move before playing
            best_res = ranker.predict_best_moves(board.fen(), candidate_count=2, depth=2)
            best_move_san = best_res.best_move_san
            best_move_uci = best_res.best_move_uci
            best_move_obj = chess.Move.from_uci(best_move_uci) if best_move_uci else None

            best_cp = best_res.candidates[0].evaluation.score_white_cp if best_res.candidates and best_res.candidates[0].evaluation.score_white_cp is not None else 0.0

            # 2. Make move
            san = board.san(move)
            board.push(move)

            # 3. Post move eval
            eval_after = PositionEvaluator.evaluate(board)
            played_cp = eval_after

            # Normalize perspective for player who moved
            player_best_cp = best_cp if turn_color == chess.WHITE else -best_cp
            player_played_cp = played_cp if turn_color == chess.WHITE else -played_cp

            # Senior Tactical Classification with Explanations
            classification = blunder_detector.classify_move(
                board_before=board_before,
                move=move,
                board_after=board,
                played_cp=player_played_cp,
                best_cp=player_best_cp,
                best_move=best_move_obj,
            )

            if turn_color == chess.WHITE:
                white_accuracies.append(classification["accuracy"])
            else:
                black_accuracies.append(classification["accuracy"])

            move_reviews.append({
                "ply": ply_idx + 1,
                "move_san": san,
                "move_uci": move.uci(),
                "player": "white" if turn_color == chess.WHITE else "black",
                "played_eval_cp": played_cp,
                "best_move_san": best_move_san,
                "best_move_uci": best_move_uci,
                "cp_loss": classification["cp_loss"],
                "accuracy": classification["accuracy"],
                "quality": classification["quality"],
                "explanation": classification["explanation"],
                "is_check": classification["is_check"],
                "is_checkmate": classification["is_checkmate"],
                "fen_after": board.fen(),
            })

        overall_white_acc = float(sum(white_accuracies) / max(1, len(white_accuracies)))
        overall_black_acc = float(sum(black_accuracies) / max(1, len(black_accuracies)))

        # Accurate ECO Opening identification
        opening_entry = opening_book.identify_opening(req.moves)

        return {
            "total_plies": len(req.moves),
            "opening": opening_entry.name,
            "eco": opening_entry.eco,
            "white_accuracy": round(overall_white_acc, 1),
            "black_accuracy": round(overall_black_acc, 1),
            "moves": move_reviews,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/review/pgn")
def review_pgn(req: PGNReviewRequest) -> Dict[str, Any]:
    """Parse raw PGN text, extract game headers and movetext, and run complete accuracy review."""
    try:
        parsed_game = pgn_service.parse_pgn_text(req.pgn)
        review_res = review_game(GameReviewRequest(
            moves=parsed_game["moves_san"],
            initial_fen=parsed_game.get("initial_fen"),
        ))

        return {
            "game_info": {
                "white": parsed_game["white"],
                "black": parsed_game["black"],
                "white_elo": parsed_game["white_elo"],
                "black_elo": parsed_game["black_elo"],
                "result": parsed_game["result"],
                "date": parsed_game["date"],
                "event": parsed_game["event"],
                "eco": parsed_game["eco"] or review_res["eco"],
                "opening": review_res["opening"],
            },
            "review": review_res,
        }
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PGN Review Error: {str(e)}")


@app.post("/api/import/lichess")
def import_lichess(req: LichessImportRequest) -> Dict[str, Any]:
    """Fetch public games from Lichess for a player username."""
    try:
        games = pgn_service.fetch_lichess_games(req.username, max_games=req.max_games)
        return {
            "platform": "lichess",
            "username": req.username,
            "games_count": len(games),
            "games": games,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lichess Import Failed: {str(e)}")


@app.post("/api/import/chesscom")
def import_chesscom(req: ChessComImportRequest) -> Dict[str, Any]:
    """Fetch public games from Chess.com for a player username."""
    try:
        games = pgn_service.fetch_chesscom_games(req.username, max_games=req.max_games)
        return {
            "platform": "chesscom",
            "username": req.username,
            "games_count": len(games),
            "games": games,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chess.com Import Failed: {str(e)}")


@app.post("/api/openings/explorer")
def opening_explorer(req: OpeningExplorerRequest) -> Dict[str, Any]:
    """Retrieve recognized opening info and candidate book continuation moves for a position."""
    try:
        # 1. Identify current opening if moves provided
        opening_entry = opening_book.identify_opening(req.moves or [])
        # 2. Get candidate continuations
        candidate_continuations = opening_book.get_candidate_book_moves(req.fen)

        return {
            "fen": req.fen,
            "eco": opening_entry.eco,
            "opening_name": opening_entry.name,
            "book_moves_count": len(candidate_continuations),
            "book_continuations": candidate_continuations,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/compare/models")
def compare_models(req: ModelComparisonRequest) -> Dict[str, Any]:
    """Module 7: Benchmark Classical ML vs Neural Network vs Minimax vs Stockfish."""
    board = chess.Board(req.fen)
    candidates = req.candidate_moves or [m.uci() for m in list(board.legal_moves)[:5]]

    benchmarks: Dict[str, Any] = {}

    # 1. Classical ML (Module 4)
    if ml_predictor.is_trained:
        t0 = time.perf_counter()
        ml_res = ml_predictor.predict_move_quality(req.fen, candidate_moves=candidates)
        t_ml = (time.perf_counter() - t0) * 1000
        benchmarks["classical_ml"] = {
            "model_name": ml_res.model_name,
            "latency_ms": round(t_ml, 2),
            "best_move": ml_res.best_move_san,
            "top_candidates": [
                {"san": c.move_san, "score": c.quality_score, "tier": c.quality_tier.value}
                for c in ml_res.candidates[:3]
            ],
        }

    # 2. Deep Learning Neural Network (Module 5)
    if neural_evaluator.is_trained:
        t0 = time.perf_counter()
        nn_eval = neural_evaluator.evaluate_position(req.fen)
        nn_ranked = neural_evaluator.evaluate_candidate_moves(req.fen, candidate_moves=candidates)
        t_nn = (time.perf_counter() - t0) * 1000
        benchmarks["deep_learning"] = {
            "model_name": f"PyTorch {neural_evaluator.model_type.upper()}",
            "device": str(neural_evaluator.device),
            "latency_ms": round(t_nn, 2),
            "position_eval_cp": nn_eval["eval_white_cp"],
            "win_probability": nn_eval["white_win_probability"],
            "best_move": nn_ranked[0]["move_san"] if nn_ranked else None,
            "top_candidates": [
                {"san": c["move_san"], "post_cp": c["post_move_eval_player_cp"], "win_prob": c["player_win_prob"]}
                for c in nn_ranked[:3]
            ],
        }

    # 3. Minimax Alpha-Beta Search (Module 2/3)
    t0 = time.perf_counter()
    minimax_res = ranker.minimax.analyze(fen=req.fen, depth=3)
    t_mm = (time.perf_counter() - t0) * 1000
    mm_eval = "+0.00"
    if minimax_res.candidates and minimax_res.candidates[0].evaluation:
        mm_eval = minimax_res.candidates[0].evaluation.display_text

    benchmarks["minimax_search"] = {
        "engine_name": "Minimax Alpha-Beta",
        "search_depth": 3,
        "latency_ms": round(t_mm, 2),
        "best_move": minimax_res.best_move_san,
        "evaluation": mm_eval,
    }

    stockfish_avail = False
    try:
        stockfish_avail = bool(ranker.stockfish.is_available())
    except Exception:
        stockfish_avail = False

    benchmarks["stockfish"] = {
        "engine_name": "Stockfish 16+ UCI",
        "available": stockfish_avail,
        "note": "Reference truth oracle when binary is installed",
    }

    return {
        "fen": req.fen,
        "benchmarks": benchmarks,
    }


# -----------------------------------------------------------------------------
# Online 1v1 Room Management Endpoints
# -----------------------------------------------------------------------------

@app.post("/api/rooms/create")
def create_room_endpoint(req: CreateRoomRequest) -> Dict[str, Any]:
    """Create a new private or public online chess room."""
    user_id = req.user_id or str(uuid.uuid4())
    username = req.username or "Player 1"

    pref = ColorPreference.RANDOM
    if req.color_preference.lower() == "white":
        pref = ColorPreference.WHITE
    elif req.color_preference.lower() == "black":
        pref = ColorPreference.BLACK

    try:
        room = room_manager.create_room(
            creator_user_id=user_id,
            creator_username=username,
            time_control_seconds=req.time_control_seconds,
            increment_seconds=req.increment_seconds,
            is_private=req.is_private,
            color_preference=pref,
        )
        return {
            "success": True,
            "room_code": room.room_code,
            "room": room.to_dict(current_user_id=user_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")


@app.post("/api/rooms/join")
def join_room_endpoint(req: JoinRoomRequest) -> Dict[str, Any]:
    """Join an existing online room using a room code."""
    user_id = req.user_id or str(uuid.uuid4())
    username = req.username or "Player 2"

    try:
        room, slot = room_manager.join_room(
            room_code=req.room_code,
            user_id=user_id,
            username=username,
        )
        return {
            "success": True,
            "room_code": room.room_code,
            "room": room.to_dict(current_user_id=user_id),
            "assigned_color": slot.assigned_color.value if slot.assigned_color else None,
            "player": slot.to_dict(),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' was not found.")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join room: {str(e)}")


@app.get("/api/rooms/public")
def list_public_rooms_endpoint() -> Dict[str, Any]:
    """List open public rooms currently waiting for an opponent."""
    rooms = room_manager.list_public_waiting_rooms()
    return {
        "count": len(rooms),
        "rooms": [r.to_dict() for r in rooms],
    }


@app.get("/api/rooms/{room_code}")
def get_room_state_endpoint(room_code: str) -> Dict[str, Any]:
    """Inspect current authoritative state of an online room."""
    room = room_manager.get_room(room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_code}' not found.")

    # Check for any elapsed timeouts on inspection
    room.check_timeouts()

    return {
        "room_code": room.room_code,
        "room": room.to_dict(),
    }


@app.post("/api/rooms/move")
def play_room_move_endpoint(req: RoomMoveRequest) -> Dict[str, Any]:
    """Execute a validated move on the authoritative game board."""
    room = room_manager.get_room(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found.")

    try:
        res = room.make_authoritative_move(user_id=req.user_id, move_str=req.move)
        return {
            "success": True,
            "played_move": res.move_record.san,
            "fen": room.engine.fen,
            "turn": room.engine.turn.value,
            "is_check": res.move_record.is_check,
            "is_game_over": room.status == RoomStatus.COMPLETED,
            "room": room.to_dict(current_user_id=req.user_id),
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except IllegalMoveError as ime:
        raise HTTPException(status_code=422, detail=f"Illegal move: {ime.move_str}")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/rooms/action")
def room_action_endpoint(req: RoomActionRequest) -> Dict[str, Any]:
    """Execute an in-game match action (resign, offer_draw, accept_draw, decline_draw, leave)."""
    room = room_manager.get_room(req.room_code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{req.room_code}' not found.")

    action = req.action.lower().strip()

    if action == "resign":
        ok = room.resign(req.user_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Cannot resign: match is not active or unauthorized user.")
    elif action == "offer_draw":
        ok = room.offer_draw(req.user_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Cannot offer draw at this time.")
    elif action == "accept_draw":
        ok = room.accept_draw(req.user_id)
        if not ok:
            raise HTTPException(status_code=400, detail="No pending draw offer to accept.")
    elif action == "decline_draw":
        room.decline_draw(req.user_id)
    elif action == "leave":
        room_manager.leave_room(req.room_code, req.user_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unrecognized action '{req.action}'.")

    return {
        "success": True,
        "action": action,
        "room": room.to_dict(current_user_id=req.user_id),
    }


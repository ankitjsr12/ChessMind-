"""FastAPI Backend Service for ChessMind AI Analytics Dashboard."""

from datetime import datetime, timezone
import math
import os
import time
from typing import Any, Dict, List, Optional
import chess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.schemas import (
    CandidatesRequest,
    GameReviewRequest,
    ModelComparisonRequest,
    MoveRequest,
    PlayAIRequest,
    PositionRequest,
)
from backend.chess_engine import ChessEngine, IllegalMoveError, InvalidFENError
from backend.chess_engine.models import PieceColor
from backend.deep_learning import NeuralPositionEvaluator
from backend.ml import MLMoveQualityPredictor
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
        },
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
    """Module 7: Move-by-move game accuracy review, opening identification, and blunder detection."""
    try:
        board = chess.Board(req.initial_fen or chess.STARTING_FEN)
        move_reviews: List[Dict[str, Any]] = []

        white_accuracies: List[float] = []
        black_accuracies: List[float] = []

        prev_eval_cp = 0.0

        for ply_idx, move_str in enumerate(req.moves):
            turn_color = board.turn
            move = board.parse_san(move_str) if move_str in [board.san(m) for m in board.legal_moves] else chess.Move.from_uci(move_str)

            # 1. Best move before playing
            best_res = ranker.predict_best_moves(board.fen(), candidate_count=2, depth=2)
            best_move_san = best_res.best_move_san
            best_move_uci = best_res.best_move_uci

            best_cp = best_res.candidates[0].evaluation.score_white_cp if best_res.candidates and best_res.candidates[0].evaluation.score_white_cp is not None else 0.0

            # 2. Make move
            san = board.san(move)
            board.push(move)

            # 3. Post move eval
            eval_after = PositionEvaluator.evaluate(board)
            played_cp = eval_after

            # Calculate cp delta from perspective of player who moved
            if turn_color == chess.WHITE:
                cp_loss = max(0.0, float(best_cp - played_cp))
            else:
                cp_loss = max(0.0, float(played_cp - best_cp))

            # Documented Accuracy Formula:
            # Acc = 103.1668 * exp(-0.04354 * cp_loss) - 3.1669 (clamped [0, 100])
            accuracy = max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * min(cp_loss, 300.0)) - 3.1669))

            # Quality classification
            if cp_loss <= 15:
                quality = "best"
            elif cp_loss <= 35:
                quality = "good"
            elif cp_loss <= 90:
                quality = "inaccuracy"
            elif cp_loss <= 200:
                quality = "mistake"
            else:
                quality = "blunder"

            if turn_color == chess.WHITE:
                white_accuracies.append(accuracy)
            else:
                black_accuracies.append(accuracy)

            move_reviews.append({
                "ply": ply_idx + 1,
                "move_san": san,
                "move_uci": move.uci(),
                "player": "white" if turn_color == chess.WHITE else "black",
                "played_eval_cp": played_cp,
                "best_move_san": best_move_san,
                "best_move_uci": best_move_uci,
                "cp_loss": round(cp_loss, 1),
                "accuracy": round(accuracy, 1),
                "quality": quality,
                "fen_after": board.fen(),
            })
            prev_eval_cp = played_cp

        overall_white_acc = float(sum(white_accuracies) / max(1, len(white_accuracies)))
        overall_black_acc = float(sum(black_accuracies) / max(1, len(black_accuracies)))

        # Opening identification heuristic based on first moves
        opening_name = "Custom / Standard Game"
        if len(req.moves) >= 2:
            m1 = req.moves[0]
            if m1 in ("e4", "e2e4"):
                m2 = req.moves[1]
                if m2 in ("e5", "e7e5"):
                    opening_name = "Open Game (King's Pawn)"
                elif m2 in ("c5", "c7c5"):
                    opening_name = "Sicilian Defense"
                elif m2 in ("e6", "e7e6"):
                    opening_name = "French Defense"
                elif m2 in ("c6", "c7c6"):
                    opening_name = "Caro-Kann Defense"
            elif m1 in ("d4", "d2d4"):
                opening_name = "Queen's Pawn Opening"

        return {
            "total_plies": len(req.moves),
            "opening": opening_name,
            "white_accuracy": round(overall_white_acc, 1),
            "black_accuracy": round(overall_black_acc, 1),
            "moves": move_reviews,
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

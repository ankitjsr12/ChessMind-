/**
 * TypeScript Data Models for ChessMind AI Analytics Dashboard.
 */

export type PieceColor = 'white' | 'black';

export type QualityTier = 'excellent' | 'good' | 'inaccuracy' | 'mistake' | 'blunder';

export interface MoveRecord {
  san: string;
  uci: string;
  from: string;
  to: string;
  fenAfter: string;
  turn: PieceColor;
}

export interface CandidateMove {
  rank: number;
  san: string;
  uci: string;
  evaluationText: string;
  scoreCentipawns?: number;
  winProbability?: number;
  qualityTier?: QualityTier;
  pv: string[];
  isTopRecommendation?: boolean;
  tacticalThreat?: string;
  opponentReplySan?: string;
  opponentReplyUci?: string;
}

export interface OpponentResponse {
  moveSan: string;
  moveUci: string;
  evaluation: string;
  pv: string[];
  isCheck: boolean;
  isCapture: boolean;
  tacticalThreat?: string;
}

export interface BoardState {
  fen: string;
  turn: PieceColor;
  isCheck: boolean;
  isCheckmate: boolean;
  isStalemate: boolean;
  isGameOver: boolean;
  legalMovesCount: number;
  fullmoveNumber: number;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  modules: {
    chess_engine: boolean;
    minimax_predictor: boolean;
    stockfish: boolean;
    opponent_search: boolean;
    ml_model_trained: boolean;
    neural_model_trained: boolean;
  };
  device: string;
}

export interface DashboardStats {
  summary: {
    total_games: number;
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
    average_accuracy: number;
  };
  move_quality_distribution: Array<{
    tier: string;
    count: number;
    percentage: number;
    color: string;
  }>;
  accuracy_trends: Array<{
    game: string;
    accuracy: number;
    opponent: string;
  }>;
  recent_games: Array<{
    id: string;
    date: string;
    white: string;
    black: string;
    result: string;
    accuracy: number;
    moves: number;
    opening: string;
  }>;
}

export interface GameReviewItem {
  ply: number;
  move_san: string;
  move_uci: string;
  player: 'white' | 'black';
  played_eval_cp: number;
  best_move_san: string;
  best_move_uci: string;
  cp_loss: number;
  accuracy: number;
  quality: QualityTier | 'best';
  fen_after: string;
}

export interface GameReviewReport {
  total_plies: number;
  opening: string;
  white_accuracy: number;
  black_accuracy: number;
  moves: GameReviewItem[];
}

export interface ModelComparisonReport {
  fen: string;
  benchmarks: {
    classical_ml?: {
      model_name: string;
      latency_ms: number;
      best_move: string;
      top_candidates: Array<{ san: string; score: number; tier: string }>;
    };
    deep_learning?: {
      model_name: string;
      device: string;
      latency_ms: number;
      position_eval_cp: number;
      win_probability: number;
      best_move: string;
      top_candidates: Array<{ san: string; post_cp: number; win_prob: number }>;
    };
    minimax_search?: {
      engine_name: string;
      search_depth: number;
      latency_ms: number;
      best_move: string;
      evaluation: string;
    };
    stockfish?: {
      engine_name: string;
      available: boolean;
      note: string;
    };
  };
}

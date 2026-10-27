/**
 * HTTP Client and Service Layer for ChessMind AI Backend API.
 */

import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  DashboardStats,
  GameReviewReport,
  HealthStatus,
  ModelComparisonReport,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ChessApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 15000,
    });
  }

  /**
   * Health and service availability status.
   */
  async getHealth(): Promise<HealthStatus> {
    const res = await this.client.get<HealthStatus>('/api/health');
    return res.data;
  }

  /**
   * Retrieve aggregate game statistics and move-quality distributions.
   */
  async getDashboardStats(): Promise<DashboardStats> {
    const res = await this.client.get<DashboardStats>('/api/dashboard/stats');
    return res.data;
  }

  /**
   * Play AI move given board FEN and difficulty level.
   */
  async playAIMove(fen: string, difficulty: 'easy' | 'medium' | 'master' | 'neural' = 'medium') {
    const res = await this.client.post('/api/engine/play-ai', { fen, difficulty });
    return res.data;
  }

  /**
   * Module 2: Predict best move, top 3 alternatives, centipawns, and principal variation.
   */
  async predictBestMoves(fen: string) {
    const res = await this.client.post('/api/predict/best-move', { fen });
    return res.data;
  }

  /**
   * Module 3: Predict adversarial opponent responses for candidate moves.
   */
  async predictOpponentResponses(fen: string, candidateMoves?: string[]) {
    const res = await this.client.post('/api/predict/opponent-response', {
      fen,
      candidate_moves: candidateMoves,
    });
    return res.data;
  }

  /**
   * Module 4: Machine Learning Candidate Move Quality Classification.
   */
  async predictCandidateQuality(fen: string, candidateMoves?: string[]) {
    const res = await this.client.post('/api/predict/candidate-quality', {
      fen,
      candidate_moves: candidateMoves,
    });
    return res.data;
  }

  /**
   * Module 5: Neural Position Evaluation & Candidate Ranking.
   */
  async predictNeuralEval(fen: string, candidateMoves?: string[]) {
    const res = await this.client.post('/api/predict/neural-eval', {
      fen,
      candidate_moves: candidateMoves,
    });
    return res.data;
  }

  /**
   * Module 7: Full game accuracy review, blunders, and evaluation graph.
   */
  async reviewGame(moves: string[], initialFen?: string): Promise<GameReviewReport> {
    const res = await this.client.post<GameReviewReport>('/api/review/game', {
      moves,
      initial_fen: initialFen,
    });
    return res.data;
  }

  /**
   * Module 7: Multi-Model Benchmark & Latency Comparison.
   */
  async compareModels(fen: string, candidateMoves?: string[]): Promise<ModelComparisonReport> {
    const res = await this.client.post<ModelComparisonReport>('/api/compare/models', {
      fen,
      candidate_moves: candidateMoves,
    });
    return res.data;
  }
}

export const api = new ChessApiService();

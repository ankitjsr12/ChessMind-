/**
 * Supabase Chess Database Service Layer
 *
 * Handles CRUD operations for Games, Moves, and Analysis against
 * Supabase PostgreSQL with Row Level Security.
 */

import { supabase } from './supabase';
import type {
  DbGame,
  DbGameMove,
  DbGameAnalysis,
  DbGameWithDetails,
  GameResult,
  PlayerColour,
  OpponentType,
} from '../types/database';

export class SupabaseChessService {
  /**
   * Helper to ensure Supabase client is available.
   */
  private static getClient() {
    if (!supabase) {
      throw new Error(
        'Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.'
      );
    }
    return supabase;
  }

  /**
   * Create a new chess game record in Supabase.
   */
  static async createGame(params: {
    playerColour: PlayerColour;
    opponentType: OpponentType;
    startingFen?: string;
    title?: string;
  }): Promise<DbGame> {
    const client = this.getClient();

    const {
      data: { user },
    } = await client.auth.getUser();

    if (!user) {
      throw new Error('You must be logged in to save games.');
    }

    const startingFen =
      params.startingFen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

    const { data, error } = await client
      .from('games')
      .insert({
        user_id: user.id,
        player_colour: params.playerColour,
        opponent_type: params.opponentType,
        result: '*',
        starting_fen: startingFen,
        current_fen: startingFen,
        pgn: '',
        title: params.title || `Game vs ${params.opponentType}`,
      })
      .select()
      .single();

    if (error) {
      throw new Error(`Failed to create game: ${error.message}`);
    }

    return data as DbGame;
  }

  /**
   * Append a move to the game_moves table and update current_fen in games.
   */
  static async appendMove(
    gameId: string,
    move: {
      moveNumber: number;
      san: string;
      uci: string;
      fenAfterMove: string;
    }
  ): Promise<DbGameMove> {
    const client = this.getClient();

    // 1. Insert move record
    const { data: moveData, error: moveError } = await client
      .from('game_moves')
      .insert({
        game_id: gameId,
        move_number: move.moveNumber,
        san: move.san,
        uci: move.uci,
        fen_after_move: move.fenAfterMove,
      })
      .select()
      .single();

    if (moveError) {
      throw new Error(`Failed to save move: ${moveError.message}`);
    }

    // 2. Update current_fen on parent game
    const { error: updateError } = await client
      .from('games')
      .update({
        current_fen: move.fenAfterMove,
      })
      .eq('id', gameId);

    if (updateError) {
      console.warn('Could not update game current_fen:', updateError.message);
    }

    return moveData as DbGameMove;
  }

  /**
   * Finalize or update game status, result, and PGN.
   */
  static async updateGameResult(
    gameId: string,
    updates: {
      result: GameResult;
      currentFen?: string;
      pgn?: string;
    }
  ): Promise<DbGame> {
    const client = this.getClient();

    const payload: Partial<DbGame> = {
      result: updates.result,
    };
    if (updates.currentFen) payload.current_fen = updates.currentFen;
    if (updates.pgn !== undefined) payload.pgn = updates.pgn;

    const { data, error } = await client
      .from('games')
      .update(payload)
      .eq('id', gameId)
      .select()
      .single();

    if (error) {
      throw new Error(`Failed to update game: ${error.message}`);
    }

    return data as DbGame;
  }

  /**
   * Retrieve all games belonging to the authenticated user.
   */
  static async listUserGames(): Promise<DbGame[]> {
    const client = this.getClient();

    const {
      data: { user },
    } = await client.auth.getUser();

    if (!user) {
      return [];
    }

    const { data, error } = await client
      .from('games')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) {
      throw new Error(`Failed to load games: ${error.message}`);
    }

    return (data || []) as DbGame[];
  }

  /**
   * Retrieve single game with all associated moves and engine analyses.
   */
  static async getGameDetails(gameId: string): Promise<DbGameWithDetails> {
    const client = this.getClient();

    // 1. Fetch game
    const { data: game, error: gameError } = await client
      .from('games')
      .select('*')
      .eq('id', gameId)
      .single();

    if (gameError || !game) {
      throw new Error(gameError?.message || 'Game not found or unauthorized.');
    }

    // 2. Fetch moves
    const { data: moves, error: movesError } = await client
      .from('game_moves')
      .select('*')
      .eq('game_id', gameId)
      .order('move_number', { ascending: true });

    if (movesError) {
      console.warn('Could not fetch game moves:', movesError.message);
    }

    // 3. Fetch analysis
    const { data: analysis, error: analysisError } = await client
      .from('game_analysis')
      .select('*')
      .eq('game_id', gameId)
      .order('created_at', { ascending: false });

    if (analysisError) {
      console.warn('Could not fetch game analysis:', analysisError.message);
    }

    return {
      ...(game as DbGame),
      moves: (moves || []) as DbGameMove[],
      analysis: (analysis || []) as DbGameAnalysis[],
    };
  }

  /**
   * Record engine analysis result linked to a game.
   */
  static async saveGameAnalysis(params: {
    gameId: string;
    bestMove: string;
    evaluationScore: number;
    searchDepth?: number;
    analysisSummary?: Record<string, any>;
  }): Promise<DbGameAnalysis> {
    const client = this.getClient();

    const { data, error } = await client
      .from('game_analysis')
      .insert({
        game_id: params.gameId,
        best_move: params.bestMove,
        evaluation_score: params.evaluationScore,
        search_depth: params.searchDepth || 3,
        analysis_summary: params.analysisSummary || {},
      })
      .select()
      .single();

    if (error) {
      throw new Error(`Failed to save analysis: ${error.message}`);
    }

    return data as DbGameAnalysis;
  }

  /**
   * Delete a game by ID (cascade deletes moves and analysis in PostgreSQL).
   */
  static async deleteGame(gameId: string): Promise<void> {
    const client = this.getClient();

    const { error } = await client.from('games').delete().eq('id', gameId);

    if (error) {
      throw new Error(`Failed to delete game: ${error.message}`);
    }
  }
}

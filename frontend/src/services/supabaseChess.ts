/**
 * Supabase Chess Database Service Layer
 *
 * Handles CRUD operations for Games, Moves, and Analysis against:
 * 1. Supabase PostgreSQL with Row Level Security when configured.
 * 2. Seamless local storage fallback when Supabase credentials are pending.
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

const LOCAL_GAMES_KEY = 'chessmind_local_games';
const LOCAL_MOVES_KEY = 'chessmind_local_moves';
const LOCAL_ANALYSIS_KEY = 'chessmind_local_analysis';

export class SupabaseChessService {
  // ---------------------------------------------------------------------------
  // Local Storage Helper Methods
  // ---------------------------------------------------------------------------
  private static getLocalGames(): DbGame[] {
    try {
      const raw = localStorage.getItem(LOCAL_GAMES_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  private static setLocalGames(games: DbGame[]) {
    try {
      localStorage.setItem(LOCAL_GAMES_KEY, JSON.stringify(games));
    } catch (err) {
      console.warn('LocalStorage save failed:', err);
    }
  }

  private static getLocalMoves(): DbGameMove[] {
    try {
      const raw = localStorage.getItem(LOCAL_MOVES_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  private static setLocalMoves(moves: DbGameMove[]) {
    try {
      localStorage.setItem(LOCAL_MOVES_KEY, JSON.stringify(moves));
    } catch (err) {
      console.warn('LocalStorage save failed:', err);
    }
  }

  private static getLocalAnalysis(): DbGameAnalysis[] {
    try {
      const raw = localStorage.getItem(LOCAL_ANALYSIS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  private static setLocalAnalysis(analysis: DbGameAnalysis[]) {
    try {
      localStorage.setItem(LOCAL_ANALYSIS_KEY, JSON.stringify(analysis));
    } catch (err) {
      console.warn('LocalStorage save failed:', err);
    }
  }

  // ---------------------------------------------------------------------------
  // Public Database API
  // ---------------------------------------------------------------------------

  /**
   * Create a new chess game record.
   */
  static async createGame(params: {
    playerColour: PlayerColour;
    opponentType: OpponentType;
    startingFen?: string;
    title?: string;
  }): Promise<DbGame> {
    const startingFen =
      params.startingFen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

    if (supabase) {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        throw new Error('You must be logged in to save games.');
      }

      const { data, error } = await supabase
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
    } else {
      // Local Mode
      const id = `game-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
      const newGame: DbGame = {
        id,
        user_id: 'local-user',
        player_colour: params.playerColour,
        opponent_type: params.opponentType,
        result: '*',
        starting_fen: startingFen,
        current_fen: startingFen,
        pgn: '',
        title: params.title || `Game vs ${params.opponentType}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const games = this.getLocalGames();
      games.unshift(newGame);
      this.setLocalGames(games);
      return newGame;
    }
  }

  /**
   * Append a move to the game_moves and update current_fen in games.
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
    if (supabase) {
      // 1. Insert move record
      const { data: moveData, error: moveError } = await supabase
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
      await supabase
        .from('games')
        .update({
          current_fen: move.fenAfterMove,
        })
        .eq('id', gameId);

      return moveData as DbGameMove;
    } else {
      // Local Mode
      const newMove: DbGameMove = {
        id: `move-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
        game_id: gameId,
        move_number: move.moveNumber,
        san: move.san,
        uci: move.uci,
        fen_after_move: move.fenAfterMove,
        created_at: new Date().toISOString(),
      };

      const allMoves = this.getLocalMoves();
      allMoves.push(newMove);
      this.setLocalMoves(allMoves);

      // Update parent game
      const games = this.getLocalGames();
      const target = games.find((g) => g.id === gameId);
      if (target) {
        target.current_fen = move.fenAfterMove;
        target.updated_at = new Date().toISOString();
        this.setLocalGames(games);
      }

      return newMove;
    }
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
    if (supabase) {
      const payload: Partial<DbGame> = {
        result: updates.result,
      };
      if (updates.currentFen) payload.current_fen = updates.currentFen;
      if (updates.pgn !== undefined) payload.pgn = updates.pgn;

      const { data, error } = await supabase
        .from('games')
        .update(payload)
        .eq('id', gameId)
        .select()
        .single();

      if (error) {
        throw new Error(`Failed to update game: ${error.message}`);
      }

      return data as DbGame;
    } else {
      // Local Mode
      const games = this.getLocalGames();
      const target = games.find((g) => g.id === gameId);
      if (target) {
        target.result = updates.result;
        if (updates.currentFen) target.current_fen = updates.currentFen;
        if (updates.pgn !== undefined) target.pgn = updates.pgn;
        target.updated_at = new Date().toISOString();
        this.setLocalGames(games);
        return target;
      }
      throw new Error('Local game not found');
    }
  }

  /**
   * Retrieve all games belonging to the active user.
   */
  static async listUserGames(): Promise<DbGame[]> {
    if (supabase) {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        return [];
      }

      const { data, error } = await supabase
        .from('games')
        .select('*')
        .order('created_at', { ascending: false });

      if (error) {
        throw new Error(`Failed to load games: ${error.message}`);
      }

      return (data || []) as DbGame[];
    } else {
      // Local Mode
      return this.getLocalGames().sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    }
  }

  /**
   * Retrieve single game with all associated moves and engine analyses.
   */
  static async getGameDetails(gameId: string): Promise<DbGameWithDetails> {
    if (supabase) {
      const { data: game, error: gameError } = await supabase
        .from('games')
        .select('*')
        .eq('id', gameId)
        .single();

      if (gameError || !game) {
        throw new Error(gameError?.message || 'Game not found or unauthorized.');
      }

      const { data: moves } = await supabase
        .from('game_moves')
        .select('*')
        .eq('game_id', gameId)
        .order('move_number', { ascending: true });

      const { data: analysis } = await supabase
        .from('game_analysis')
        .select('*')
        .eq('game_id', gameId)
        .order('created_at', { ascending: false });

      return {
        ...(game as DbGame),
        moves: (moves || []) as DbGameMove[],
        analysis: (analysis || []) as DbGameAnalysis[],
      };
    } else {
      // Local Mode
      const games = this.getLocalGames();
      const game = games.find((g) => g.id === gameId);
      if (!game) {
        throw new Error('Game not found.');
      }

      const moves = this.getLocalMoves()
        .filter((m) => m.game_id === gameId)
        .sort((a, b) => a.move_number - b.move_number);

      const analysis = this.getLocalAnalysis()
        .filter((a) => a.game_id === gameId)
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      return {
        ...game,
        moves,
        analysis,
      };
    }
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
    if (supabase) {
      const { data, error } = await supabase
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
    } else {
      // Local Mode
      const newAnalysis: DbGameAnalysis = {
        id: `analysis-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
        game_id: params.gameId,
        best_move: params.bestMove,
        evaluation_score: params.evaluationScore,
        search_depth: params.searchDepth || 3,
        analysis_summary: params.analysisSummary || {},
        created_at: new Date().toISOString(),
      };

      const all = this.getLocalAnalysis();
      all.unshift(newAnalysis);
      this.setLocalAnalysis(all);
      return newAnalysis;
    }
  }

  /**
   * Delete a game by ID (cascade deletes moves and analysis).
   */
  static async deleteGame(gameId: string): Promise<void> {
    if (supabase) {
      const { error } = await supabase.from('games').delete().eq('id', gameId);
      if (error) {
        throw new Error(`Failed to delete game: ${error.message}`);
      }
    } else {
      // Local Mode
      const games = this.getLocalGames().filter((g) => g.id !== gameId);
      this.setLocalGames(games);

      const moves = this.getLocalMoves().filter((m) => m.game_id !== gameId);
      this.setLocalMoves(moves);

      const analysis = this.getLocalAnalysis().filter((a) => a.game_id !== gameId);
      this.setLocalAnalysis(analysis);
    }
  }
}

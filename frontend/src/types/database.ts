/**
 * TypeScript Data Models matching the Supabase PostgreSQL Schema:
 * tables: profiles, games, game_moves, game_analysis.
 */

export interface UserProfile {
  id: string;
  display_name: string | null;
  created_at: string;
}

export type PlayerColour = 'white' | 'black';

export type GameResult = '1-0' | '0-1' | '1/2-1/2' | '*';

export type OpponentType = 'easy' | 'medium' | 'master' | 'neural' | 'human' | string;

export interface DbGame {
  id: string;
  user_id: string;
  player_colour: PlayerColour;
  opponent_type: OpponentType;
  result: GameResult;
  starting_fen: string;
  current_fen: string;
  pgn: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface DbGameMove {
  id: string;
  game_id: string;
  move_number: number;
  san: string;
  uci: string;
  fen_after_move: string;
  created_at: string;
}

export interface DbGameAnalysis {
  id: string;
  game_id: string;
  best_move: string;
  evaluation_score: number;
  search_depth: number;
  analysis_summary: Record<string, any>;
  created_at: string;
}

export interface DbGameWithDetails extends DbGame {
  moves?: DbGameMove[];
  analysis?: DbGameAnalysis[];
}

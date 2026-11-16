/**
 * Client-Side In-Browser Chess AI Fallback Engine
 *
 * Provides instant AI responses using lightweight minimax alpha-beta search
 * directly in JavaScript. Ensures the game is 100% playable even when the
 * Python FastAPI backend is offline or during standalone Vercel deployments.
 */

import { Chess } from 'chess.js';

const PIECE_VALUES: Record<string, number> = {
  p: 100,
  n: 320,
  b: 330,
  r: 500,
  q: 900,
  k: 20000,
};

// Simplified piece-square bonus tables for basic positional awareness
const PAWN_PST = [
  0, 0, 0, 0, 0, 0, 0, 0,
  50, 50, 50, 50, 50, 50, 50, 50,
  10, 10, 20, 30, 30, 20, 10, 10,
  5, 5, 10, 25, 25, 10, 5, 5,
  0, 0, 0, 20, 20, 0, 0, 0,
  5, -5, -10, 0, 0, -10, -5, 5,
  5, 10, 10, -20, -20, 10, 10, 5,
  0, 0, 0, 0, 0, 0, 0, 0,
];

const KNIGHT_PST = [
  -50, -40, -30, -30, -30, -30, -40, -50,
  -40, -20, 0, 5, 5, 0, -20, -40,
  -30, 5, 10, 15, 15, 10, 5, -30,
  -30, 0, 15, 20, 20, 15, 0, -30,
  -30, 5, 15, 20, 20, 15, 5, -30,
  -30, 0, 10, 15, 15, 10, 0, -30,
  -40, -20, 0, 0, 0, 0, -20, -40,
  -50, -40, -30, -30, -30, -30, -40, -50,
];

function evaluateBoard(board: Chess): number {
  let score = 0;
  const boardMatrix = board.board();

  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      const piece = boardMatrix[r][c];
      if (!piece) continue;

      const val = PIECE_VALUES[piece.type] || 0;
      let pstBonus = 0;
      const idx = r * 8 + c;

      if (piece.type === 'p') {
        pstBonus = piece.color === 'w' ? PAWN_PST[idx] : PAWN_PST[63 - idx];
      } else if (piece.type === 'n') {
        pstBonus = piece.color === 'w' ? KNIGHT_PST[idx] : KNIGHT_PST[63 - idx];
      }

      const totalVal = val + pstBonus;
      score += piece.color === 'w' ? totalVal : -totalVal;
    }
  }

  return score;
}

function minimax(
  game: Chess,
  depth: number,
  alpha: number,
  beta: number,
  isMaximizing: boolean
): number {
  if (depth === 0 || game.isGameOver()) {
    if (game.isCheckmate()) {
      return isMaximizing ? -99999 : 99999;
    }
    if (game.isDraw()) return 0;
    return evaluateBoard(game);
  }

  const moves = game.moves({ verbose: true });

  if (isMaximizing) {
    let maxEval = -Infinity;
    for (const move of moves) {
      game.move(move);
      const evalScore = minimax(game, depth - 1, alpha, beta, false);
      game.undo();
      maxEval = Math.max(maxEval, evalScore);
      alpha = Math.max(alpha, evalScore);
      if (beta <= alpha) break;
    }
    return maxEval;
  } else {
    let minEval = Infinity;
    for (const move of moves) {
      game.move(move);
      const evalScore = minimax(game, depth - 1, alpha, beta, true);
      game.undo();
      minEval = Math.min(minEval, evalScore);
      beta = Math.min(beta, evalScore);
      if (beta <= alpha) break;
    }
    return minEval;
  }
}

/**
 * Calculates a client-side AI response move in milliseconds.
 */
export function getClientFallbackMove(
  fen: string,
  difficulty: 'easy' | 'medium' | 'master' | 'neural' = 'medium'
): { uci: string; san: string } | null {
  const game = new Chess(fen);
  if (game.isGameOver()) return null;

  const moves = game.moves({ verbose: true });
  if (moves.length === 0) return null;

  // Search depth based on difficulty
  const searchDepth = difficulty === 'easy' ? 1 : 2;
  const isWhite = game.turn() === 'w';

  let bestMove = moves[0];
  let bestScore = isWhite ? -Infinity : Infinity;

  // Shuffle slightly so games don't play identically every time
  const shuffledMoves = [...moves].sort(() => Math.random() - 0.5);

  for (const move of shuffledMoves) {
    game.move(move);
    const score = minimax(game, searchDepth - 1, -Infinity, Infinity, !isWhite);
    game.undo();

    if (isWhite) {
      if (score > bestScore) {
        bestScore = score;
        bestMove = move;
      }
    } else {
      if (score < bestScore) {
        bestScore = score;
        bestMove = move;
      }
    }
  }

  const uci = `${bestMove.from}${bestMove.to}${bestMove.promotion || ''}`;
  return { uci, san: bestMove.san };
}


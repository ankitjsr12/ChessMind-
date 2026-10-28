import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Chess } from 'chess.js';
import type { Square } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import { api } from '../services/api';
import type { MoveRecord } from '../types';
import type { DbGame } from '../types/database';
import { MoveHistory } from '../components/MoveHistory';
import { useAuth } from '../context/AuthContext';
import { SupabaseChessService } from '../services/supabaseChess';

interface PlayPageProps {
  initialGameToResume?: DbGame | null;
  onOpenAuth?: () => void;
}

export const PlayPage: React.FC<PlayPageProps> = ({ initialGameToResume, onOpenAuth }) => {
  const { user } = useAuth();
  const [game, setGame] = useState<Chess>(() => {
    if (initialGameToResume?.current_fen) {
      try {
        return new Chess(initialGameToResume.current_fen);
      } catch {
        return new Chess();
      }
    }
    return new Chess();
  });

  const [history, setHistory] = useState<MoveRecord[]>([]);
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'master' | 'neural'>(
    (initialGameToResume?.opponent_type as any) || 'medium'
  );
  const [orientation, setOrientation] = useState<'white' | 'black'>(
    initialGameToResume?.player_colour || 'white'
  );
  const [isAiThinking, setIsAiThinking] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('White to move');
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [possibleMoves, setPossibleMoves] = useState<Square[]>([]);
  const [gameOverMessage, setGameOverMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  // Cloud Save State
  const [savedGameId, setSavedGameId] = useState<string | null>(initialGameToResume?.id || null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(
    initialGameToResume ? 'Resumed saved cloud game' : null
  );

  // Load existing moves if resuming
  useEffect(() => {
    if (initialGameToResume?.id) {
      setSavedGameId(initialGameToResume.id);
      SupabaseChessService.getGameDetails(initialGameToResume.id)
        .then((details) => {
          if (details.moves && details.moves.length > 0) {
            const reconstructed: MoveRecord[] = details.moves.map((m, idx) => ({
              san: m.san,
              uci: m.uci,
              from: m.uci.slice(0, 2),
              to: m.uci.slice(2, 4),
              fenAfter: m.fen_after_move,
              turn: idx % 2 === 0 ? 'white' : 'black',
            }));
            setHistory(reconstructed);
          }
        })
        .catch((err) => console.warn('Could not restore game moves:', err));
    }
  }, [initialGameToResume]);

  // Compute captured pieces
  const capturedPieces = useMemo(() => {
    const counts = {
      white: { p: 8, n: 2, b: 2, r: 2, q: 1 },
      black: { p: 8, n: 2, b: 2, r: 2, q: 1 },
    };
    const board = game.board();
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const piece = board[r][c];
        if (piece) {
          const color = piece.color === 'w' ? 'white' : 'black';
          const type = piece.type;
          if (type in counts[color]) {
            counts[color][type as keyof typeof counts.white]--;
          }
        }
      }
    }
    const captured = { white: [] as string[], black: [] as string[] };
    const symbols: Record<string, { w: string; b: string }> = {
      p: { w: '♙', b: '♟' },
      n: { w: '♘', b: '♞' },
      b: { w: '♗', b: '♝' },
      r: { w: '♖', b: '♜' },
      q: { w: '♕', b: '♛' },
    };
    for (const [type, count] of Object.entries(counts.white)) {
      for (let i = 0; i < count; i++) captured.white.push(symbols[type].w);
    }
    for (const [type, count] of Object.entries(counts.black)) {
      for (let i = 0; i < count; i++) captured.black.push(symbols[type].b);
    }
    return captured;
  }, [game]);

  const updateStatus = useCallback(
    (currentGame: Chess, activeGameId?: string | null) => {
      let resultStr: '1-0' | '0-1' | '1/2-1/2' | '*' = '*';
      if (currentGame.isCheckmate()) {
        const winner = currentGame.turn() === 'w' ? 'Black' : 'White';
        const msg = `Checkmate! ${winner} wins.`;
        setStatusMessage(msg);
        setGameOverMessage(msg);
        resultStr = currentGame.turn() === 'w' ? '0-1' : '1-0';
      } else if (currentGame.isDraw()) {
        let reason = 'Draw';
        if (currentGame.isStalemate()) reason = 'Stalemate';
        else if (currentGame.isThreefoldRepetition()) reason = 'Threefold Repetition';
        else if (currentGame.isInsufficientMaterial()) reason = 'Insufficient Material';
        const msg = `Game drawn by ${reason}.`;
        setStatusMessage(msg);
        setGameOverMessage(msg);
        resultStr = '1/2-1/2';
      } else if (currentGame.inCheck()) {
        setStatusMessage(`${currentGame.turn() === 'w' ? 'White' : 'Black'} is in check!`);
      } else {
        setStatusMessage(`${currentGame.turn() === 'w' ? 'White' : 'Black'} to move`);
        setGameOverMessage(null);
      }

      // Automatically sync final game result to Supabase if saved
      const targetId = activeGameId !== undefined ? activeGameId : savedGameId;
      if (targetId && resultStr !== '*') {
        SupabaseChessService.updateGameResult(targetId, {
          result: resultStr,
          currentFen: currentGame.fen(),
          pgn: currentGame.pgn(),
        }).catch((err) => console.warn('Could not finalize game in Supabase:', err));
      }
    },
    [savedGameId]
  );

  const triggerAiMove = useCallback(
    async (currentGame: Chess) => {
      if (currentGame.isGameOver()) return;

      setIsAiThinking(true);
      setApiError(null);

      try {
        const fen = currentGame.fen();
        const data = await api.playAIMove(fen, difficulty);

        if (data && (data.move || data.ai_move_uci)) {
          const moveUci = data.move || data.ai_move_uci;
          const from = moveUci.slice(0, 2) as Square;
          const to = moveUci.slice(2, 4) as Square;
          const promotion = moveUci.length > 4 ? moveUci[4] : undefined;

          const newGame = new Chess(currentGame.fen());
          const moveResult = newGame.move({ from, to, promotion: promotion || 'q' });

          if (moveResult) {
            setGame(newGame);
            setHistory((prev) => [
              ...prev,
              {
                san: moveResult.san,
                uci: moveResult.lan || `${moveResult.from}${moveResult.to}`,
                from: moveResult.from,
                to: moveResult.to,
                fenAfter: newGame.fen(),
                turn: 'black',
              },
            ]);
            updateStatus(newGame);

            // Auto-sync AI move to Supabase if game is saved
            if (savedGameId) {
              SupabaseChessService.appendMove(savedGameId, {
                moveNumber: history.length + 1,
                san: moveResult.san,
                uci: moveResult.lan || `${moveResult.from}${moveResult.to}`,
                fenAfterMove: newGame.fen(),
              }).catch((err) => console.warn('Error syncing AI move to Supabase:', err));
            }
          }
        }
      } catch (err: any) {
        setApiError(err.response?.data?.detail || err.message || 'AI move request failed.');
      } finally {
        setIsAiThinking(false);
      }
    },
    [difficulty, updateStatus, savedGameId, history.length]
  );

  const onDrop = (sourceSquare: Square, targetSquare: Square): boolean => {
    if (isAiThinking || game.isGameOver()) return false;

    const piece = game.get(sourceSquare);
    if (!piece || (orientation === 'white' && piece.color !== 'w') || (orientation === 'black' && piece.color !== 'b')) {
      return false;
    }

    try {
      const newGame = new Chess(game.fen());
      const move = newGame.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q',
      });

      if (!move) return false;

      setGame(newGame);
      setSelectedSquare(null);
      setPossibleMoves([]);

      const newRecord: MoveRecord = {
        san: move.san,
        uci: move.lan || `${move.from}${move.to}`,
        from: move.from,
        to: move.to,
        fenAfter: newGame.fen(),
        turn: move.color === 'w' ? 'white' : 'black',
      };

      setHistory((prev) => [...prev, newRecord]);
      updateStatus(newGame);

      // Auto-sync player move to Supabase if game is saved
      if (savedGameId) {
        SupabaseChessService.appendMove(savedGameId, {
          moveNumber: history.length + 1,
          san: move.san,
          uci: move.lan || `${move.from}${move.to}`,
          fenAfterMove: newGame.fen(),
        }).catch((err) => console.warn('Error syncing player move to Supabase:', err));
      }

      if (!newGame.isGameOver()) {
        setTimeout(() => triggerAiMove(newGame), 250);
      }

      return true;
    } catch {
      return false;
    }
  };

  const onSquareClick = (square: Square) => {
    if (isAiThinking || game.isGameOver()) return;

    if (selectedSquare) {
      if (selectedSquare === square) {
        setSelectedSquare(null);
        setPossibleMoves([]);
        return;
      }

      const moveSuccessful = onDrop(selectedSquare, square);
      if (moveSuccessful) return;
    }

    const piece = game.get(square);
    if (piece && ((orientation === 'white' && piece.color === 'w') || (orientation === 'black' && piece.color === 'b'))) {
      setSelectedSquare(square);
      const moves = game.moves({ square, verbose: true });
      setPossibleMoves(moves.map((m) => m.to as Square));
    } else {
      setSelectedSquare(null);
      setPossibleMoves([]);
    }
  };

  const handleRestart = () => {
    const freshGame = new Chess();
    setGame(freshGame);
    setHistory([]);
    setSelectedSquare(null);
    setPossibleMoves([]);
    setGameOverMessage(null);
    setApiError(null);
    setSavedGameId(null);
    setSaveSuccessMsg(null);
    updateStatus(freshGame, null);
  };

  const handleUndo = () => {
    if (history.length === 0 || isAiThinking) return;
    const movesToUndo = history.length >= 2 ? 2 : 1;
    const newHistory = history.slice(0, history.length - movesToUndo);

    const reconstructed = new Chess();
    for (const item of newHistory) {
      try {
        reconstructed.move(item.san);
      } catch {
        // Fallback
      }
    }

    setGame(reconstructed);
    setHistory(newHistory);
    setSelectedSquare(null);
    setPossibleMoves([]);
    updateStatus(reconstructed);
  };

  // Explicit Save to Cloud Action
  const handleSaveToCloud = async () => {
    if (!user) {
      if (onOpenAuth) onOpenAuth();
      else alert('Please sign in to save your match to Supabase PostgreSQL.');
      return;
    }

    setIsSaving(true);
    setSaveSuccessMsg(null);
    setApiError(null);

    try {
      const created = await SupabaseChessService.createGame({
        playerColour: orientation,
        opponentType: difficulty,
        startingFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        title: `Match vs ${difficulty.toUpperCase()} AI`,
      });

      setSavedGameId(created.id);

      // Save all existing moves into the new game
      for (let i = 0; i < history.length; i++) {
        const item = history[i];
        await SupabaseChessService.appendMove(created.id, {
          moveNumber: i + 1,
          san: item.san,
          uci: item.uci,
          fenAfterMove: item.fenAfter,
        });
      }

      // If game is over, save result immediately
      if (game.isGameOver()) {
        const result = game.isCheckmate() ? (game.turn() === 'w' ? '0-1' : '1-0') : '1/2-1/2';
        await SupabaseChessService.updateGameResult(created.id, {
          result,
          currentFen: game.fen(),
          pgn: game.pgn(),
        });
      }

      setSaveSuccessMsg('Game saved to Supabase! Future moves will sync automatically.');
    } catch (err: any) {
      setApiError(err.message || 'Failed to save game to Supabase.');
    } finally {
      setIsSaving(false);
    }
  };

  const customSquareStyles = useMemo(() => {
    const styles: Record<string, React.CSSProperties> = {};

    if (selectedSquare) {
      styles[selectedSquare] = {
        backgroundColor: 'rgba(255, 255, 0, 0.4)',
      };
    }

    possibleMoves.forEach((sq) => {
      const isOccupied = Boolean(game.get(sq));
      styles[sq] = {
        background: isOccupied
          ? 'radial-gradient(circle, transparent 20%, rgba(0, 0, 0, 0.25) 21%, transparent 70%)'
          : 'radial-gradient(circle, rgba(0, 0, 0, 0.2) 25%, transparent 26%)',
        borderRadius: isOccupied ? '50%' : undefined,
      };
    });

    if (game.inCheck()) {
      const kingSquare = game
        .board()
        .flatMap((row, r) =>
          row.map((piece, c) => {
            if (piece && piece.type === 'k' && piece.color === game.turn()) {
              const file = String.fromCharCode(97 + c);
              const rank = 8 - r;
              return `${file}${rank}` as Square;
            }
            return null;
          })
        )
        .find(Boolean);

      if (kingSquare) {
        styles[kingSquare] = {
          backgroundColor: 'rgba(220, 38, 38, 0.65)',
        };
      }
    }

    return styles;
  }, [game, selectedSquare, possibleMoves]);

  return (
    <div>
      {/* Page Title & Controls Bar */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="page-title">Play Chess</h1>
          <p className="page-description">
            Play against intelligent AI models with move validation and cloud PostgreSQL persistence.
          </p>
        </div>

        {/* Cloud Sync Status / Save Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {savedGameId ? (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '4px',
                backgroundColor: '#f0fdf4',
                border: '1px solid #bbf7d0',
                fontSize: '0.78rem',
                color: '#166534',
                fontWeight: 600,
              }}
              title={`Game ID: ${savedGameId}`}
            >
              <span>☁️ Cloud Synced</span>
            </div>
          ) : (
            <button
              onClick={handleSaveToCloud}
              disabled={isSaving}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 12px' }}
              title="Save current game to Supabase PostgreSQL"
            >
              {isSaving ? 'Saving...' : '☁️ Save to Cloud'}
            </button>
          )}

          {/* AI Difficulty Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)' }}>AI Opponent:</span>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as any)}
              disabled={isAiThinking}
              className="select-input"
            >
              <option value="easy">Easy (Minimax D1)</option>
              <option value="medium">Medium (Minimax D3)</option>
              <option value="master">Master (Stockfish / Hybrid)</option>
              <option value="neural">Neural Network (PyTorch)</option>
            </select>
          </div>
        </div>
      </div>

      {apiError && (
        <div className="banner-error" style={{ marginBottom: '16px' }}>
          <span>⚠️ {apiError}</span>
        </div>
      )}

      {saveSuccessMsg && (
        <div
          style={{
            marginBottom: '16px',
            padding: '8px 14px',
            borderRadius: '4px',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            fontSize: '0.82rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>✓ {saveSuccessMsg}</span>
          <button
            onClick={() => setSaveSuccessMsg(null)}
            style={{ background: 'none', border: 'none', color: '#166534', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Chessboard + Move History Layout */}
      <div className="board-layout">
        {/* Left: Traditional Chessboard */}
        <div style={{ display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '520px' }}>
          {/* Opponent Info & Captured White Pieces */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', padding: '0 4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>
                ChessMind AI ({difficulty.toUpperCase()})
              </span>
              {isAiThinking && (
                <span style={{ fontSize: '0.72rem', color: 'var(--chess-blue)', fontWeight: 600 }}>
                  Thinking...
                </span>
              )}
            </div>
            <div className="captured-bar">
              {capturedPieces.white.map((sym, i) => (
                <span key={i} title="Captured White piece">{sym}</span>
              ))}
            </div>
          </div>

          {/* Chessboard Container */}
          <div
            className="board-container"
            style={{
              width: '100%',
              aspectRatio: '1/1',
              position: 'relative',
            }}
          >
            {gameOverMessage && (
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  backgroundColor: 'rgba(15, 23, 42, 0.75)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 20,
                  borderRadius: '6px',
                  color: '#ffffff',
                  padding: '20px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '8px' }}>Game Finished</div>
                <div style={{ fontSize: '1rem', color: '#cbd5e1', marginBottom: '20px' }}>{gameOverMessage}</div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button onClick={handleRestart} className="btn btn-primary">
                    Play Again
                  </button>
                  {!savedGameId && user && (
                    <button onClick={handleSaveToCloud} disabled={isSaving} className="btn btn-secondary" style={{ backgroundColor: '#ffffff', color: '#0f172a' }}>
                      {isSaving ? 'Saving...' : 'Save to Cloud'}
                    </button>
                  )}
                </div>
              </div>
            )}

            <Chessboard
              options={{
                position: game.fen(),
                boardOrientation: orientation,
                onPieceDrop: ({ sourceSquare, targetSquare }) =>
                  onDrop(sourceSquare as Square, (targetSquare || '') as Square),
                onSquareClick: ({ square }) => onSquareClick(square as Square),
                squareStyles: customSquareStyles,
                darkSquareStyle: { backgroundColor: '#769656' },   // Classic Lichess / Chess.com green
                lightSquareStyle: { backgroundColor: '#eeeed2' },  // Classic clean cream
                animationDurationInMs: 180,
              }}
            />
          </div>

          {/* Player Info & Captured Black Pieces */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', padding: '0 4px' }}>
            <div style={{ fontSize: '0.88rem', fontWeight: 600 }}>
              You ({orientation === 'white' ? 'White' : 'Black'})
            </div>
            <div className="captured-bar">
              {capturedPieces.black.map((sym, i) => (
                <span key={i} title="Captured Black piece">{sym}</span>
              ))}
            </div>
          </div>

          {/* Game Controls */}
          <div style={{ display: 'flex', gap: '8px', marginTop: '16px', justifyContent: 'center' }}>
            <button
              onClick={handleUndo}
              disabled={isAiThinking || history.length === 0}
              className="btn btn-secondary"
            >
              Undo Move
            </button>
            <button
              onClick={() => setOrientation((o) => (o === 'white' ? 'black' : 'white'))}
              className="btn btn-secondary"
            >
              Flip Board
            </button>
            <button onClick={handleRestart} className="btn btn-secondary" style={{ color: 'var(--chess-red)' }}>
              New Game
            </button>
          </div>
        </div>

        {/* Right: Status and Move History */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Current Status</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: game.inCheck() ? 'var(--chess-red)' : 'var(--text-main)' }}>
              {statusMessage}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Turn: {game.turn() === 'w' ? 'White' : 'Black'} · Move #{Math.floor(history.length / 2) + 1}
            </div>
          </div>

          <MoveHistory history={history} height={380} />
        </div>
      </div>
    </div>
  );
};

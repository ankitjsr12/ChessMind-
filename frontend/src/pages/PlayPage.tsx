import React, { useState, useCallback, useMemo } from 'react';
import { Chess } from 'chess.js';
import type { Square } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import { api } from '../services/api';
import type { MoveRecord } from '../types';
import { MoveHistory } from '../components/MoveHistory';

export const PlayPage: React.FC = () => {
  const [game, setGame] = useState<Chess>(new Chess());
  const [history, setHistory] = useState<MoveRecord[]>([]);
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'master' | 'neural'>('medium');
  const [orientation, setOrientation] = useState<'white' | 'black'>('white');
  const [isAiThinking, setIsAiThinking] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('White to move');
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [possibleMoves, setPossibleMoves] = useState<Square[]>([]);
  const [gameOverMessage, setGameOverMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

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

  const updateStatus = useCallback((currentGame: Chess) => {
    if (currentGame.isCheckmate()) {
      const winner = currentGame.turn() === 'w' ? 'Black' : 'White';
      const msg = `Checkmate! ${winner} wins.`;
      setStatusMessage(msg);
      setGameOverMessage(msg);
    } else if (currentGame.isDraw()) {
      let reason = 'Draw';
      if (currentGame.isStalemate()) reason = 'Stalemate';
      else if (currentGame.isThreefoldRepetition()) reason = 'Threefold Repetition';
      else if (currentGame.isInsufficientMaterial()) reason = 'Insufficient Material';
      const msg = `Game drawn by ${reason}.`;
      setStatusMessage(msg);
      setGameOverMessage(msg);
    } else if (currentGame.inCheck()) {
      setStatusMessage(`${currentGame.turn() === 'w' ? 'White' : 'Black'} is in check!`);
    } else {
      setStatusMessage(`${currentGame.turn() === 'w' ? 'White' : 'Black'} to move`);
      setGameOverMessage(null);
    }
  }, []);

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
          }
        }
      } catch (err: any) {
        setApiError(err.response?.data?.detail || err.message || 'AI move request failed.');
      } finally {
        setIsAiThinking(false);
      }
    },
    [difficulty, updateStatus]
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
      const moveSuccess = onDrop(selectedSquare, square);
      if (moveSuccess) return;
    }

    const piece = game.get(square);
    if (piece && piece.color === game.turn()) {
      setSelectedSquare(square);
      const moves = game.moves({ square, verbose: true });
      setPossibleMoves(moves.map((m) => m.to as Square));
    } else {
      setSelectedSquare(null);
      setPossibleMoves([]);
    }
  };

  const handleUndo = () => {
    if (isAiThinking || history.length === 0) return;
    const newGame = new Chess();
    const newHistory = history.slice(0, Math.max(0, history.length - 2));
    for (const h of newHistory) newGame.move(h.san);
    setGame(newGame);
    setHistory(newHistory);
    setSelectedSquare(null);
    setPossibleMoves([]);
    updateStatus(newGame);
    setGameOverMessage(null);
  };

  const handleRestart = () => {
    const newGame = new Chess();
    setGame(newGame);
    setHistory([]);
    setSelectedSquare(null);
    setPossibleMoves([]);
    setGameOverMessage(null);
    setApiError(null);
    updateStatus(newGame);
  };

  const customSquareStyles = useMemo(() => {
    const styles: Record<string, React.CSSProperties> = {};

    if (selectedSquare) {
      styles[selectedSquare] = {
        backgroundColor: 'rgba(255, 255, 0, 0.4)',
      };
    }

    possibleMoves.forEach((sq) => {
      styles[sq] = {
        background: 'radial-gradient(circle, rgba(0, 0, 0, 0.25) 25%, transparent 26%)',
        borderRadius: '50%',
        cursor: 'pointer',
      };
    });

    if (history.length > 0) {
      const last = history[history.length - 1];
      styles[last.from] = { backgroundColor: 'rgba(255, 255, 0, 0.2)' };
      styles[last.to] = { backgroundColor: 'rgba(255, 255, 0, 0.3)' };
    }

    return styles;
  }, [selectedSquare, possibleMoves, history]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Play Chess</h1>
          <p className="page-description">Play a standard chess game against the ChessMind AI engine.</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>AI Difficulty:</span>
          <select
            className="select-input"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as any)}
            disabled={isAiThinking}
          >
            <option value="easy">Easy (Shallow Search)</option>
            <option value="medium">Medium (Minimax Depth 3)</option>
            <option value="master">Master (Alpha-Beta)</option>
            <option value="neural">Neural Network (ResNet)</option>
          </select>
        </div>
      </div>

      {apiError && (
        <div className="banner-error">
          <span>⚠️ {apiError}</span>
        </div>
      )}

      {gameOverMessage && (
        <div className="banner-info" style={{ justifyContent: 'space-between' }}>
          <span><b>Game Over:</b> {gameOverMessage}</span>
          <button onClick={handleRestart} className="btn btn-primary" style={{ padding: '4px 10px', fontSize: '0.78rem' }}>
            Play Again
          </button>
        </div>
      )}

      <div className="chess-grid">
        {/* Left: Chessboard */}
        <div>
          {/* Opponent Info & Captured White Pieces */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', padding: '0 4px' }}>
            <div style={{ fontSize: '0.88rem', fontWeight: 600 }}>
              AI ({difficulty.toUpperCase()})
              {isAiThinking && (
                <span style={{ marginLeft: '8px', fontSize: '0.78rem', color: 'var(--chess-blue)', fontWeight: 500 }}>
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

          {/* Board */}
          <div className="board-container" style={{ margin: '0 auto', maxWidth: '520px', width: '100%' }}>
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
              You (White)
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

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Chess } from 'chess.js';
import type { Square } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import type { Arrow } from 'react-chessboard';
import { api } from '../services/api';

const PRESET_POSITIONS: Record<string, { label: string; fen: string }> = {
  start: {
    label: 'Standard Opening',
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  },
  ruy_lopez: {
    label: 'Ruy Lopez: Morphy Defense',
    fen: 'r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4',
  },
  sicilian: {
    label: 'Sicilian Defense: Open Line',
    fen: 'r1bqkbnr/pp1ppppp/2n5/8/3NP3/8/PPP2PPP/RNBQKB1R b KQkq - 0 4',
  },
  middlegame: {
    label: 'Tactical Middlegame',
    fen: 'r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 7',
  },
};

interface PredictionData {
  fen: string;
  side_to_move: string;
  best_move?: { uci: string; san: string };
  candidates: Array<{
    rank: number;
    uci: string;
    san: string;
    evaluation: string;
    score_cp?: number;
    pv: string[];
  }>;
  search_depth: number;
  analysis_time_ms: number;
  engine_name: string;
  nodes_evaluated?: number;
}

export const PredictionPage: React.FC = () => {
  const [game, setGame] = useState<Chess>(new Chess());
  const [fenInput, setFenInput] = useState<string>(new Chess().fen());
  const [selectedPreset, setSelectedPreset] = useState<string>('start');
  const [prediction, setPrediction] = useState<PredictionData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const requestPrediction = useCallback(async (currentFen: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.predictBestMoves(currentFen);
      const rawCandidates = data.candidate_moves || data.top_candidates || [];

      const parsedCandidates = rawCandidates.map((c: any) => ({
        rank: c.rank,
        uci: c.uci || c.move,
        san: c.san,
        evaluation:
          typeof c.evaluation === 'object' ? c.evaluation.display_text : (c.evaluation || '+0.0'),
        score_cp:
          typeof c.evaluation === 'object' ? c.evaluation.score_white_cp : (c.evaluation_cp || 0),
        pv: c.pv_san || c.pv || [],
      }));

      setPrediction({
        fen: currentFen,
        side_to_move: data.side_to_move || (currentFen.includes(' w ') ? 'white' : 'black'),
        best_move: data.best_move ? { uci: data.best_move.uci, san: data.best_move.san } : undefined,
        candidates: parsedCandidates,
        search_depth: data.search_depth || 3,
        analysis_time_ms: data.analysis_time_ms || 0,
        engine_name: data.engine_name || 'Minimax Engine',
        nodes_evaluated: data.nodes_evaluated,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to predict move.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    requestPrediction(game.fen());
  }, [game, requestPrediction]);

  const onDrop = (sourceSquare: Square, targetSquare: Square): boolean => {
    try {
      const newGame = new Chess(game.fen());
      const move = newGame.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q',
      });
      if (!move) return false;
      setGame(newGame);
      setFenInput(newGame.fen());
      return true;
    } catch {
      return false;
    }
  };

  const handlePresetSelect = (key: string) => {
    setSelectedPreset(key);
    const p = PRESET_POSITIONS[key];
    if (p) {
      try {
        const newGame = new Chess(p.fen);
        setGame(newGame);
        setFenInput(p.fen);
      } catch {
        // ignore
      }
    }
  };

  const handleFenSubmit = () => {
    try {
      const newGame = new Chess(fenInput.trim());
      setGame(newGame);
      setError(null);
    } catch {
      setError('Invalid FEN format.');
    }
  };

  // Generate suggested move arrow on board
  const bestMoveArrow: Arrow[] = useMemo(() => {
    const moveUci = prediction?.best_move?.uci;
    if (moveUci && moveUci.length >= 4) {
      const from = moveUci.slice(0, 2);
      const to = moveUci.slice(2, 4);
      return [{ startSquare: from, endSquare: to, color: 'rgba(21, 128, 61, 0.85)' }];
    }
    return [];
  }, [prediction]);

  const bestMove = prediction?.best_move;
  const alternatives = prediction?.candidates.filter((c) => c.rank > 1).slice(0, 2) || [];
  const bestCandidate = prediction?.candidates[0];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Move Prediction</h1>
          <p className="page-description">
            Get the engine's recommended best move and alternative candidate responses for any position.
          </p>
        </div>

        {/* Preset Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Position Preset:</span>
          <select
            className="select-input"
            value={selectedPreset}
            onChange={(e) => handlePresetSelect(e.target.value)}
          >
            {Object.entries(PRESET_POSITIONS).map(([key, item]) => (
              <option key={key} value={key}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="banner-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Manual FEN Input */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <input
          type="text"
          className="text-input"
          value={fenInput}
          onChange={(e) => setFenInput(e.target.value)}
          placeholder="Enter FEN string..."
          style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}
        />
        <button onClick={handleFenSubmit} className="btn btn-secondary">
          Update Board
        </button>
        <button
          onClick={() => requestPrediction(game.fen())}
          disabled={loading}
          className="btn btn-primary"
        >
          {loading ? 'Analyzing...' : 'Predict Move'}
        </button>
      </div>

      <div className="chess-grid">
        {/* Left: Interactive Chessboard */}
        <div>
          <div className="board-container" style={{ margin: '0 auto', maxWidth: '500px', width: '100%' }}>
            <Chessboard
              options={{
                position: game.fen(),
                boardOrientation: 'white',
                arrows: bestMoveArrow,
                onPieceDrop: ({ sourceSquare, targetSquare }) =>
                  onDrop(sourceSquare as Square, (targetSquare || '') as Square),
                darkSquareStyle: { backgroundColor: '#769656' },
                lightSquareStyle: { backgroundColor: '#eeeed2' },
                animationDurationInMs: 180,
              }}
            />
          </div>

          <div style={{ textAlign: 'center', marginTop: '10px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Drag and drop pieces to customize the position.
          </div>
        </div>

        {/* Right: Prediction Results Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Best Suggested Move Card */}
          <div className="panel" style={{ padding: '16px' }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
              Best Suggested Move
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: '6px', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                <span style={{ fontSize: '1.8rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#15803d' }}>
                  {loading ? '...' : bestMove ? bestMove.san : 'None'}
                </span>
                {bestMove && (
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    ({bestMove.uci})
                  </span>
                )}
              </div>

              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Evaluation</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-main)' }}>
                  {loading ? '...' : bestCandidate?.evaluation || '0.0'}
                </div>
              </div>
            </div>

            {/* Move Explanation */}
            <div
              style={{
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: '#f8fafc',
                border: '1px solid var(--border-color)',
                fontSize: '0.85rem',
                color: 'var(--text-main)',
                lineHeight: 1.45,
              }}
            >
              <b>Why this move:</b>{' '}
              {bestMove ? (
                <>
                  Playing <code>{bestMove.san}</code> is evaluated as the highest-scoring candidate.
                  It develops an active piece, contests central space, and prevents opponent counterplay.
                </>
              ) : (
                'Make a move or choose a position to calculate the best reply.'
              )}
            </div>
          </div>

          {/* Alternative Moves */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Alternative Candidate Moves</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Top alternatives</span>
            </div>

            <div style={{ padding: '12px 16px' }}>
              {alternatives.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                  No alternative moves found.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {alternatives.map((alt) => (
                    <div
                      key={alt.uci}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 12px',
                        backgroundColor: '#f8fafc',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ color: 'var(--text-dim)', fontWeight: 600 }}>#{alt.rank}</span>
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.95rem' }}>
                          {alt.san}
                        </span>
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}>
                          ({alt.uci})
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                          {alt.evaluation}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Search Depth & Analysis Status */}
          <div className="panel" style={{ padding: '12px 16px' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
              Engine Status
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', fontSize: '0.8rem' }}>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Engine:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                  {prediction?.engine_name || 'Minimax Search'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Search Depth:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                  Depth {prediction?.search_depth || 3}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)' }}>Latency:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                  {prediction?.analysis_time_ms ? `${prediction.analysis_time_ms.toFixed(1)} ms` : '—'}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

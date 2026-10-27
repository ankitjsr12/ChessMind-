import React, { useState, useEffect, useCallback } from 'react';
import { Chessboard } from 'react-chessboard';
import { api } from '../services/api';
import type { DashboardStats, GameReviewReport, GameReviewItem } from '../types';

const SAMPLE_GAMES: Record<string, { title: string; moves: string[] }> = {
  opera: {
    title: 'Morphy vs Duke Karl (Opera Game)',
    moves: [
      'e4', 'e5', 'Nf3', 'd6', 'd4', 'Bg4', 'dxe5', 'Bxf3', 'Qxf3', 'dxe5',
      'Bc4', 'Nf6', 'Qb3', 'Qe7', 'Nc3', 'c6', 'Bg5', 'b5', 'Nxb5', 'cxb5',
      'Bxb5+', 'Nbd7', 'O-O-O', 'Rd8', 'Rxd7', 'Rxd7', 'Rd1', 'Qe6', 'Bxd7+', 'Nxd7',
      'Qb8+', 'Nxb8', 'Rd8#'
    ],
  },
  ruy_lopez: {
    title: 'Ruy Lopez: Morphy Defense',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'a6', 'Ba4', 'Nf6', 'O-O', 'Be7', 'Re1', 'b5', 'Bb3', 'd6'],
  },
  italian: {
    title: 'Italian Game Classic Line',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5', 'c3', 'Nf6', 'd4', 'exd4', 'cxd4', 'Bb4+'],
  },
};

export const HistoryPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activeReviewKey, setActiveReviewKey] = useState<string | null>('opera');
  const [reviewReport, setReviewReport] = useState<GameReviewReport | null>(null);
  const [currentPlyIndex, setCurrentPlyIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load games from backend stats
  useEffect(() => {
    const fetchGames = async () => {
      try {
        const data = await api.getDashboardStats();
        setStats(data);
      } catch (err: any) {
        setError(err.message || 'Could not load game history.');
      }
    };
    fetchGames();
  }, []);

  // Run review for selected game
  const loadReview = useCallback(async (moves: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.reviewGame(moves);
      setReviewReport(data);
      setCurrentPlyIndex(0);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to review game.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeReviewKey && SAMPLE_GAMES[activeReviewKey]) {
      loadReview(SAMPLE_GAMES[activeReviewKey].moves);
    }
  }, [activeReviewKey, loadReview]);

  const currentMove: GameReviewItem | undefined = reviewReport?.moves[currentPlyIndex];
  const currentFen = currentMove?.fen_after || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Game History</h1>
          <p className="page-description">
            Review past games, view accuracy percentages, and inspect moves.
          </p>
        </div>
      </div>

      {error && (
        <div className="banner-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Recent Games Table */}
      <div className="panel" style={{ marginBottom: '24px', overflow: 'hidden' }}>
        <div className="panel-header">
          <span className="panel-title">Completed Games</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {stats?.recent_games.length || 0} recorded matches
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>White</th>
                <th>Black</th>
                <th>Result</th>
                <th>Accuracy</th>
                <th>Moves</th>
                <th>Opening</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {stats?.recent_games.map((g) => (
                <tr key={g.id}>
                  <td style={{ color: 'var(--text-muted)' }}>{g.date}</td>
                  <td style={{ fontWeight: 600 }}>{g.white}</td>
                  <td style={{ fontWeight: 600 }}>{g.black}</td>
                  <td>
                    <span
                      style={{
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: '3px',
                        fontSize: '0.75rem',
                        backgroundColor:
                          g.result === '1-0' ? '#dcfce7' : g.result === '0-1' ? '#fee2e2' : '#fef3c7',
                        color:
                          g.result === '1-0' ? '#15803d' : g.result === '0-1' ? '#dc2626' : '#d97706',
                      }}
                    >
                      {g.result}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600, color: 'var(--chess-blue)' }}>{g.accuracy}%</td>
                  <td>{g.moves} plies</td>
                  <td style={{ color: 'var(--text-muted)' }}>{g.opening}</td>
                  <td>
                    <button
                      onClick={() => setActiveReviewKey('opera')}
                      className="btn btn-secondary"
                      style={{ padding: '3px 8px', fontSize: '0.75rem' }}
                    >
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Move-by-Move Review Panel */}
      <div className="panel" style={{ padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>
              Game Review: {SAMPLE_GAMES[activeReviewKey || 'opera']?.title}
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Opening detected: <b style={{ color: 'var(--chess-blue)' }}>{reviewReport?.opening || 'Detecting...'}</b>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Select Game:</span>
            <select
              className="select-input"
              value={activeReviewKey || 'opera'}
              onChange={(e) => setActiveReviewKey(e.target.value)}
            >
              {Object.entries(SAMPLE_GAMES).map(([key, item]) => (
                <option key={key} value={key}>
                  {item.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Accuracies */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
          <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>White Accuracy</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#15803d' }}>
              {reviewReport ? `${reviewReport.white_accuracy}%` : '...'}
            </div>
          </div>
          <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Black Accuracy</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#2563eb' }}>
              {reviewReport ? `${reviewReport.black_accuracy}%` : '...'}
            </div>
          </div>
          <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Total Plies</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              {reviewReport ? reviewReport.total_plies : '...'}
            </div>
          </div>
        </div>

        {/* Board & Stepper View */}
        <div className="chess-grid" style={{ gridTemplateColumns: 'minmax(320px, 460px) minmax(300px, 1fr)' }}>
          <div>
            <div className="board-container" style={{ margin: '0 auto', maxWidth: '440px', width: '100%' }}>
              <Chessboard
                options={{
                  position: currentFen,
                  allowDragging: false,
                  boardOrientation: 'white',
                  darkSquareStyle: { backgroundColor: '#769656' },
                  lightSquareStyle: { backgroundColor: '#eeeed2' },
                  animationDurationInMs: 180,
                }}
              />
            </div>

            {/* Stepper Buttons */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'center', alignItems: 'center' }}>
              <button
                onClick={() => setCurrentPlyIndex(0)}
                disabled={currentPlyIndex === 0}
                className="btn btn-secondary"
              >
                |◀ First
              </button>
              <button
                onClick={() => setCurrentPlyIndex((p) => Math.max(0, p - 1))}
                disabled={currentPlyIndex === 0}
                className="btn btn-secondary"
              >
                ◀ Prev
              </button>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, padding: '0 8px', fontFamily: 'var(--font-mono)' }}>
                {currentMove ? `${currentMove.ply} / ${reviewReport?.total_plies}` : '0 / 0'}
              </span>
              <button
                onClick={() => setCurrentPlyIndex((p) => Math.min((reviewReport?.moves.length || 1) - 1, p + 1))}
                disabled={!reviewReport || currentPlyIndex >= reviewReport.moves.length - 1}
                className="btn btn-secondary"
              >
                Next ▶
              </button>
              <button
                onClick={() => setCurrentPlyIndex((reviewReport?.moves.length || 1) - 1)}
                disabled={!reviewReport || currentPlyIndex >= reviewReport.moves.length - 1}
                className="btn btn-secondary"
              >
                Last ▶|
              </button>
            </div>
          </div>

          {/* Move Details */}
          <div>
            {currentMove ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ padding: '12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Ply {currentMove.ply} ({currentMove.player.toUpperCase()})
                    </span>
                    <span className={`badge badge-${currentMove.quality}`}>
                      {currentMove.quality}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '6px' }}>
                    <div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Played</div>
                      <div style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
                        {currentMove.move_san}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Best Move</div>
                      <div style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#15803d' }}>
                        {currentMove.best_move_san}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    <span>Centipawn Loss: <b>{currentMove.cp_loss} cp</b></span>
                    <span>Accuracy: <b>{currentMove.accuracy}%</b></span>
                  </div>
                </div>

                <div style={{ padding: '10px 12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <b>Accuracy Formula:</b> Calculated using exponential score decay:
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', marginTop: '4px', color: 'var(--text-main)' }}>
                    accuracy = clamp(103.17 * exp(-0.0435 * Δcp) - 3.17, 0, 100)
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                {loading ? 'Analyzing game plies...' : 'Select a move to inspect details.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

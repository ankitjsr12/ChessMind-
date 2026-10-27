import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Chessboard } from 'react-chessboard';
import { api } from '../services/api';
import type { GameReviewReport, GameReviewItem, QualityTier } from '../types';
import { EvaluationTimelineChart } from '../charts/EvaluationTimelineChart';
import {
  FileSearch,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
  Award,
  BookOpen,
  Info,
} from 'lucide-react';

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
  italian: {
    title: 'Italian Game Classic Line',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5', 'c3', 'Nf6', 'd4', 'exd4', 'cxd4', 'Bb4+'],
  },
  ruy_lopez: {
    title: 'Ruy Lopez: Morphy Defense',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'a6', 'Ba4', 'Nf6', 'O-O', 'Be7', 'Re1', 'b5', 'Bb3', 'd6'],
  },
};

const getTierBadge = (quality: QualityTier | 'best') => {
  switch (quality) {
    case 'best':
    case 'excellent':
      return <span className="badge badge-excellent">{quality}</span>;
    case 'good':
      return <span className="badge badge-good">good</span>;
    case 'inaccuracy':
      return <span className="badge badge-inaccuracy">inaccuracy</span>;
    case 'mistake':
      return <span className="badge badge-mistake">mistake</span>;
    case 'blunder':
      return <span className="badge badge-blunder">blunder</span>;
    default:
      return <span className="badge badge-good">{quality}</span>;
  }
};

export const ReviewPage: React.FC = () => {
  const [selectedGameKey, setSelectedGameKey] = useState<string>('opera');
  const [report, setReport] = useState<GameReviewReport | null>(null);
  const [currentPlyIndex, setCurrentPlyIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Trigger game review analysis
  const analyzeGame = useCallback(async (moves: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.reviewGame(moves);
      setReport(data);
      setCurrentPlyIndex(data.moves.length > 0 ? 0 : 0);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to review game.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Run on mount or game select
  useEffect(() => {
    const game = SAMPLE_GAMES[selectedGameKey];
    if (game) {
      analyzeGame(game.moves);
    }
  }, [selectedGameKey, analyzeGame]);

  const currentMove: GameReviewItem | undefined = report?.moves[currentPlyIndex];
  const currentFen = currentMove?.fen_after || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  // Count blunders and mistakes
  const blunderCount = useMemo(() => {
    if (!report) return { mistakes: 0, blunders: 0 };
    let mistakes = 0;
    let blunders = 0;
    for (const m of report.moves) {
      if (m.quality === 'blunder') blunders++;
      if (m.quality === 'mistake') mistakes++;
    }
    return { mistakes, blunders };
  }, [report]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner & Game Selector */}
      <div
        className="card"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          padding: '16px 24px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: 'rgba(6, 182, 212, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <FileSearch size={22} color="#06b6d4" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
              Full Game Accuracy & Blunder Review
            </h2>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Opening: <b style={{ color: '#38bdf8' }}>{report?.opening || 'Detecting...'}</b>
            </div>
          </div>
        </div>

        {/* Preset Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BookOpen size={16} color="var(--text-muted)" />
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            Select Game:
          </span>
          <select
            value={selectedGameKey}
            onChange={(e) => setSelectedGameKey(e.target.value)}
            disabled={loading}
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-main)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 12px',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {Object.entries(SAMPLE_GAMES).map(([key, item]) => (
              <option key={key} value={key}>
                {item.title} ({item.moves.length} moves)
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertTriangle size={18} color="#ef4444" />
          <span>{error}</span>
        </div>
      )}

      {/* Accuracy KPI Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">White Accuracy</span>
          <div className="stat-value" style={{ color: '#34d399' }}>
            {report ? `${report.white_accuracy}%` : '...'}
          </div>
          <div className="stat-subtext">Exponential score decay</div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Black Accuracy</span>
          <div className="stat-value" style={{ color: '#60a5fa' }}>
            {report ? `${report.black_accuracy}%` : '...'}
          </div>
          <div className="stat-subtext">Exponential score decay</div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Mistakes & Blunders</span>
          <div className="stat-value" style={{ color: blunderCount.blunders > 0 ? '#f87171' : '#34d399' }}>
            {report ? `${blunderCount.blunders} Blunders / ${blunderCount.mistakes} Mistakes` : '...'}
          </div>
          <div className="stat-subtext">Centipawn loss thresholds</div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Total Plies</span>
          <div className="stat-value">
            {report ? report.total_plies : '...'}
          </div>
          <div className="stat-subtext">Analyzed move-by-move</div>
        </div>
      </div>

      {/* Evaluation Graph Across Plies */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Game Evaluation Curve</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Interactive graph (click any ply to jump board position)
            </p>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', fontWeight: 600 }}>
            Active Ply: {currentMove ? currentMove.ply : 1} / {report?.total_plies || 1}
          </span>
        </div>

        <EvaluationTimelineChart
          moves={report?.moves || []}
          selectedPly={currentMove?.ply}
          onSelectPly={(ply) => {
            const idx = report?.moves.findIndex((m) => m.ply === ply);
            if (idx !== undefined && idx >= 0) {
              setCurrentPlyIndex(idx);
            }
          }}
          height={180}
        />
      </div>

      {/* Move-by-Move Review Stepper & Board Layout */}
      <div className="chess-layout" style={{ gridTemplateColumns: 'minmax(340px, 480px) minmax(320px, 1fr)' }}>
        {/* Left Column: Board */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="board-wrapper" style={{ margin: '0 auto', maxWidth: '480px', width: '100%' }}>
            <Chessboard
              options={{
                position: currentFen,
                allowDragging: false,
                boardOrientation: 'white',
                darkSquareStyle: { backgroundColor: '#334155' },
                lightSquareStyle: { backgroundColor: '#94a3b8' },
                animationDurationInMs: 200,
              }}
            />
          </div>

          {/* Stepper Controls */}
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', alignItems: 'center' }}>
            <button
              onClick={() => setCurrentPlyIndex(0)}
              disabled={currentPlyIndex === 0}
              className="btn btn-secondary"
              title="First move"
            >
              <ChevronsLeft size={16} />
            </button>
            <button
              onClick={() => setCurrentPlyIndex((p) => Math.max(0, p - 1))}
              disabled={currentPlyIndex === 0}
              className="btn btn-secondary"
              title="Previous move"
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, padding: '0 12px', color: 'var(--text-main)' }}>
              {currentMove ? `${currentMove.ply} / ${report?.total_plies}` : '0 / 0'}
            </span>
            <button
              onClick={() => setCurrentPlyIndex((p) => Math.min((report?.moves.length || 1) - 1, p + 1))}
              disabled={!report || currentPlyIndex >= report.moves.length - 1}
              className="btn btn-secondary"
              title="Next move"
            >
              Next <ChevronRight size={16} />
            </button>
            <button
              onClick={() => setCurrentPlyIndex((report?.moves.length || 1) - 1)}
              disabled={!report || currentPlyIndex >= report.moves.length - 1}
              className="btn btn-secondary"
              title="Last move"
            >
              <ChevronsRight size={16} />
            </button>
          </div>
        </div>

        {/* Right Column: Move Details & Formula Explanation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {currentMove && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="card-header" style={{ margin: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Award size={18} color="var(--accent-primary)" />
                  <h3 className="card-title">Ply {currentMove.ply} Move Analysis</h3>
                </div>
                {getTierBadge(currentMove.quality)}
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  padding: '14px',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Played Move</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '1.2rem', fontWeight: 800, color: '#ffffff' }}>
                    {currentMove.move_san}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Player: {currentMove.player.toUpperCase()}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Engine Best Move</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '1.2rem', fontWeight: 800, color: '#34d399' }}>
                    {currentMove.best_move_san}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: currentMove.cp_loss > 0 ? '#f87171' : '#34d399' }}>
                    Loss: {currentMove.cp_loss} cp
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Calculated Accuracy:</span>
                <span style={{ fontWeight: 800, color: '#38bdf8' }}>{currentMove.accuracy}%</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Post-Move Position Eval:</span>
                <span style={{ fontWeight: 700 }}>
                  {currentMove.played_eval_cp > 0 ? `+${(currentMove.played_eval_cp / 100).toFixed(2)}` : (currentMove.played_eval_cp / 100).toFixed(2)} pawns
                </span>
              </div>
            </div>
          )}

          {/* Documented Accuracy Formula Card */}
          <div
            className="card"
            style={{
              backgroundColor: 'rgba(99, 102, 241, 0.05)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Info size={16} color="#818cf8" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#c7d2fe' }}>
                Documented Accuracy Formula
              </span>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '8px' }}>
              Accuracy evaluates each move relative to the best engine alternative using an exponential loss decay:
            </p>
            <code
              style={{
                display: 'block',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(0, 0, 0, 0.4)',
                fontSize: '0.78rem',
                color: '#34d399',
                fontFamily: 'monospace',
              }}
            >
              Accuracy = clamp(103.1668 · exp(-0.04354 · Δcp) - 3.1669, 0, 100)
            </code>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: '8px' }}>
              Zero centipawn loss yields 100% accuracy, while blunders exceeding 300 centipawns exponentially approach 0%.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

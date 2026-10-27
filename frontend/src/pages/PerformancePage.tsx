import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { ModelComparisonReport } from '../types';

const BENCHMARK_POSITIONS: Record<string, { label: string; fen: string }> = {
  start: {
    label: 'Standard Starting Position',
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  },
  tactical: {
    label: 'Tactical Middlegame (Morphy Defense)',
    fen: 'r1bqk2r/pppp1ppp/2n5/1B2p3/4n3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 1 6',
  },
  endgame: {
    label: 'Rook & Pawn Endgame',
    fen: '8/5pk1/4p1p1/7p/4RP1P/6P1/r4PK1/8 w - - 0 35',
  },
};

export const PerformancePage: React.FC = () => {
  const [selectedPosKey, setSelectedPosKey] = useState<string>('start');
  const [report, setReport] = useState<ModelComparisonReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const runBenchmark = useCallback(async (fen: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.compareModels(fen);
      setReport(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to benchmark models.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const pos = BENCHMARK_POSITIONS[selectedPosKey];
    if (pos) {
      runBenchmark(pos.fen);
    }
  }, [selectedPosKey, runBenchmark]);

  const benchmarks = report?.benchmarks;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Model Performance</h1>
          <p className="page-description">
            Benchmark inference latency and move predictions across Classical ML, Deep Learning, and Minimax search.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Benchmark Position:</span>
          <select
            className="select-input"
            value={selectedPosKey}
            onChange={(e) => setSelectedPosKey(e.target.value)}
          >
            {Object.entries(BENCHMARK_POSITIONS).map(([key, item]) => (
              <option key={key} value={key}>
                {item.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => runBenchmark(BENCHMARK_POSITIONS[selectedPosKey].fen)}
            disabled={loading}
            className="btn btn-secondary"
          >
            {loading ? 'Measuring...' : 'Re-run Benchmark'}
          </button>
        </div>
      </div>

      {error && (
        <div className="banner-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Latency Comparison Overview */}
      <div className="panel" style={{ padding: '16px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '12px' }}>
          Measured Inference Latency
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          <div style={{ padding: '12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Classical ML (XGBoost)</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#15803d', fontFamily: 'var(--font-mono)' }}>
              {loading ? '...' : `${benchmarks?.classical_ml?.latency_ms ?? 0} ms`}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>Feature Vector Classifier</div>
          </div>

          <div style={{ padding: '12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Neural ResNet ({benchmarks?.deep_learning?.device?.toUpperCase() || 'MPS'})</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#2563eb', fontFamily: 'var(--font-mono)' }}>
              {loading ? '...' : `${benchmarks?.deep_learning?.latency_ms ?? 0} ms`}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>18-channel Tensor Model</div>
          </div>

          <div style={{ padding: '12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Minimax Search (Depth 3)</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
              {loading ? '...' : `${benchmarks?.minimax_search?.latency_ms ?? 0} ms`}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>Alpha-Beta Tree Search</div>
          </div>
        </div>
      </div>

      {/* Model Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Classical ML */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">1. Classical ML (Module 4)</span>
            <span className="badge badge-excellent">Sub-10ms</span>
          </div>

          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Model Architecture</div>
              <div style={{ fontWeight: 600 }}>{benchmarks?.classical_ml?.model_name || 'XGBoost / Random Forest'}</div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Top Recommended Move</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#15803d' }}>
                {loading ? '...' : benchmarks?.classical_ml?.best_move || '—'}
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Top Candidate Scores:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {benchmarks?.classical_ml?.top_candidates?.map((c, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '4px 8px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '3px',
                      fontSize: '0.8rem',
                    }}
                  >
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{c.san}</span>
                    <span style={{ color: 'var(--text-muted)' }}>Score: {c.score.toFixed(2)}</span>
                    <span className={`badge badge-${c.tier}`}>{c.tier}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Neural Network */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">2. Deep Neural Net (Module 5)</span>
            <span className="badge badge-good">PyTorch</span>
          </div>

          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Architecture & Hardware</div>
              <div style={{ fontWeight: 600 }}>
                18-Channel ResNet CNN ({benchmarks?.deep_learning?.device?.toUpperCase() || 'MPS'})
              </div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Position Eval & Win Probability</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#2563eb' }}>
                  {loading ? '...' : `${benchmarks?.deep_learning?.position_eval_cp ?? 0} cp`}
                </span>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  ({((benchmarks?.deep_learning?.win_probability ?? 0.5) * 100).toFixed(1)}% win chance)
                </span>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                Neural Candidate Ranking:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {benchmarks?.deep_learning?.top_candidates?.map((c, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '4px 8px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '3px',
                      fontSize: '0.8rem',
                    }}
                  >
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{c.san}</span>
                    <span style={{ color: 'var(--text-muted)' }}>Post: {c.post_cp} cp</span>
                    <span style={{ fontWeight: 600, color: '#2563eb' }}>{(c.win_prob * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Minimax & Stockfish */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">3. Minimax & Stockfish (Module 2)</span>
            <span className="badge badge-inaccuracy">Search</span>
          </div>

          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Search Algorithm</div>
              <div style={{ fontWeight: 600 }}>Minimax with Alpha-Beta Pruning (Depth 3)</div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Calculated Best Move</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
                  {loading ? '...' : benchmarks?.minimax_search?.best_move || '—'}
                </span>
                <span style={{ fontSize: '0.9rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {benchmarks?.minimax_search?.evaluation}
                </span>
              </div>
            </div>

            <div style={{ padding: '10px 12px', backgroundColor: '#f8fafc', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '3px' }}>
                Stockfish UCI Reference
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                {benchmarks?.stockfish?.note || 'Standard UCI engine interface supported for ground-truth comparison.'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

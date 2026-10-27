import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { ModelComparisonReport } from '../types';
import {
  Scale,
  Zap,
  Cpu,
  Brain,
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  Timer,
} from 'lucide-react';

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

export const ModelComparisonPage: React.FC = () => {
  const [selectedPosKey, setSelectedPosKey] = useState<string>('start');
  const [customFen, setCustomFen] = useState<string>(BENCHMARK_POSITIONS.start.fen);
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
      setCustomFen(pos.fen);
      runBenchmark(pos.fen);
    }
  }, [selectedPosKey, runBenchmark]);

  const handlePositionChange = (key: string) => {
    setSelectedPosKey(key);
    const pos = BENCHMARK_POSITIONS[key];
    if (pos) {
      setCustomFen(pos.fen);
      runBenchmark(pos.fen);
    }
  };

  const benchmarks = report?.benchmarks;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
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
              backgroundColor: 'rgba(139, 92, 246, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Scale size={22} color="#a78bfa" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
              Multi-Model Benchmark & Latency Comparison
            </h2>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Head-to-head comparison of Classical ML, Deep Neural Networks & Alpha-Beta Minimax
            </div>
          </div>
        </div>

        {/* Position Selectors */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {Object.entries(BENCHMARK_POSITIONS).map(([key, item]) => (
            <button
              key={key}
              onClick={() => handlePositionChange(key)}
              className={selectedPosKey === key ? 'btn btn-primary' : 'btn btn-secondary'}
              style={{ fontSize: '0.78rem', padding: '6px 12px' }}
            >
              {item.label}
            </button>
          ))}
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
          <AlertCircle size={18} color="#ef4444" />
          <span>{error}</span>
        </div>
      )}

      {/* Latency Comparison Summary Bar */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div className="card-header" style={{ margin: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Timer size={18} color="var(--accent-cyan)" />
            <h3 className="card-title">Measured Inference Latencies</h3>
          </div>
          <button
            onClick={() => runBenchmark(customFen)}
            disabled={loading}
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <RefreshCw size={14} className={loading ? 'spin-icon' : ''} />
            Re-benchmark
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          {[
            {
              name: 'Classical ML (XGBoost/RF)',
              time: benchmarks?.classical_ml?.latency_ms ?? 0,
              color: '#10b981',
              type: 'Sub-10ms Inference',
            },
            {
              name: 'Deep Neural Net (ResNet)',
              time: benchmarks?.deep_learning?.latency_ms ?? 0,
              color: '#6366f1',
              type: `PyTorch ${benchmarks?.deep_learning?.device?.toUpperCase() || 'MPS'}`,
            },
            {
              name: 'Minimax Engine (Alpha-Beta)',
              time: benchmarks?.minimax_search?.latency_ms ?? 0,
              color: '#06b6d4',
              type: 'Depth 3 Search',
            },
          ].map((item) => (
            <div
              key={item.name}
              style={{
                padding: '14px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid var(--border-color)',
              }}
            >
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                {item.name}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '1.6rem', fontWeight: 800, color: item.color }}>
                  {loading ? '...' : `${item.time} ms`}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>latency</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                {item.type}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Model Benchmark Comparison Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Card 1: Classical Machine Learning */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Zap size={16} color="#10b981" />
                <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
                  Module 4: Classical ML
                </h4>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                {benchmarks?.classical_ml?.model_name || 'XGBoost / Random Forest Classifier'}
              </p>
            </div>
            <span className="badge badge-excellent">Fast</span>
          </div>

          <div
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.2)',
            }}
          >
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Recommended Move</div>
            <div style={{ fontFamily: 'monospace', fontSize: '1.3rem', fontWeight: 800, color: '#34d399' }}>
              {loading ? '...' : benchmarks?.classical_ml?.best_move || '—'}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
              Top Candidate Predictions:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {benchmarks?.classical_ml?.top_candidates?.slice(0, 4).map((c, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    fontSize: '0.8rem',
                  }}
                >
                  <span style={{ fontFamily: 'monospace', fontWeight: 700 }}>{c.san}</span>
                  <span style={{ color: 'var(--text-muted)' }}>Score: {c.score.toFixed(2)}</span>
                  <span style={{ textTransform: 'uppercase', fontSize: '0.7rem', color: '#34d399', fontWeight: 700 }}>
                    {c.tier}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Card 2: Deep Learning Neural Network */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Brain size={16} color="#818cf8" />
                <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
                  Module 5: Neural ResNet
                </h4>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                {benchmarks?.deep_learning?.model_name || '18-channel CNN Position Evaluator'}
              </p>
            </div>
            <span className="badge badge-good">Neural</span>
          </div>

          <div
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
          >
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Position Strength & Win Prob</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '1.3rem', fontWeight: 800, color: '#818cf8' }}>
                {loading ? '...' : `${benchmarks?.deep_learning?.position_eval_cp ?? 0} cp`}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                ({((benchmarks?.deep_learning?.win_probability ?? 0.5) * 100).toFixed(1)}% win)
              </span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px' }}>
              Neural Candidate Ranking:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {benchmarks?.deep_learning?.top_candidates?.slice(0, 4).map((c, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    fontSize: '0.8rem',
                  }}
                >
                  <span style={{ fontFamily: 'monospace', fontWeight: 700 }}>{c.san}</span>
                  <span style={{ color: 'var(--text-muted)' }}>Eval: {c.post_cp} cp</span>
                  <span style={{ fontSize: '0.75rem', color: '#818cf8', fontWeight: 700 }}>
                    {(c.win_prob * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Card 3: Minimax & Stockfish Reference */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Cpu size={16} color="#06b6d4" />
                <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
                  Module 2/3: Minimax & Reference
                </h4>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                Alpha-Beta Search & Stockfish UCI Bridge
              </p>
            </div>
            <span className="badge badge-inaccuracy">Search</span>
          </div>

          <div
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(6, 182, 212, 0.08)',
              border: '1px solid rgba(6, 182, 212, 0.2)',
            }}
          >
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Search Depth 3 Recommendation</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '1.3rem', fontWeight: 800, color: '#22d3ee' }}>
                {loading ? '...' : benchmarks?.minimax_search?.best_move || '—'}
              </span>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)' }}>
                {benchmarks?.minimax_search?.evaluation}
              </span>
            </div>
          </div>

          <div
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-color)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
              <ShieldCheck size={15} color="#10b981" />
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#fff' }}>
                Stockfish UCI Reference
              </span>
            </div>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
              {benchmarks?.stockfish?.note || 'Standard UCI Stockfish engine integrated for ground truth calibration.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

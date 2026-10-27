import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { DashboardStats, HealthStatus } from '../types';
import { QualityDistributionChart } from '../charts/QualityDistributionChart';
import {
  Trophy,
  Swords,
  TrendingUp,
  Target,
  CheckCircle2,
  AlertTriangle,
  Play,
  Brain,
  History,
  Cpu,
} from 'lucide-react';
import type { PageId } from '../components/Navigation';

interface DashboardPageProps {
  health: HealthStatus | null;
  onNavigate: (page: PageId) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ health, onNavigate }) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchStats = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getDashboardStats();
        if (isMounted) {
          setStats(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to fetch dashboard statistics from backend.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    fetchStats();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Top Banner / Hero */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(99, 102, 241, 0.15) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '20px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>
            ChessMind AI Analytics Dashboard
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', maxWidth: '640px' }}>
            Multi-engine chess analytics platform powered by adversarial minimax search, supervised candidate quality classifiers, and neural ResNet evaluation.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button onClick={() => onNavigate('play')} className="btn btn-primary">
            <Play size={16} /> Play vs AI
          </button>
          <button onClick={() => onNavigate('analysis')} className="btn btn-secondary">
            <Brain size={16} /> Live Analysis
          </button>
        </div>
      </div>

      {/* Error Banner */}
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

      {/* KPI Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="stat-label">Total Games</span>
            <Swords size={18} color="#818cf8" />
          </div>
          <div className="stat-value">
            {loading ? '...' : stats?.summary.total_games ?? 0}
          </div>
          <div className="stat-subtext">Recorded across all modes</div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="stat-label">Win Rate</span>
            <Trophy size={18} color="#10b981" />
          </div>
          <div className="stat-value" style={{ color: '#34d399' }}>
            {loading ? '...' : `${stats?.summary.win_rate ?? 0}%`}
          </div>
          <div className="stat-subtext">
            {stats ? `${stats.summary.wins}W / ${stats.summary.losses}L / ${stats.summary.draws}D` : ''}
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="stat-label">Average Accuracy</span>
            <Target size={18} color="#06b6d4" />
          </div>
          <div className="stat-value">
            {loading ? '...' : `${stats?.summary.average_accuracy ?? 0}%`}
          </div>
          <div className="stat-subtext">Documented exponential formula</div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="stat-label">Neural Engine</span>
            <Cpu size={18} color="#f59e0b" />
          </div>
          <div className="stat-value" style={{ fontSize: '1.4rem', textTransform: 'capitalize' }}>
            {health ? health.device : 'Active'}
          </div>
          <div className="stat-subtext">18-channel ResNet Evaluator</div>
        </div>
      </div>

      {/* Charts & Distribution Section */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1.2fr) minmax(280px, 1fr)', gap: '24px' }}>
        {/* Move Quality Distribution */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Move-Quality Distribution</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Classification across analyzed positions
              </p>
            </div>
            <TrendingUp size={18} color="var(--accent-primary)" />
          </div>

          <QualityDistributionChart
            data={stats?.move_quality_distribution || []}
            height={240}
          />

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-around',
              marginTop: '16px',
              paddingTop: '16px',
              borderTop: '1px solid var(--border-color)',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            {stats?.move_quality_distribution.map((item) => (
              <div key={item.tier} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{item.tier}</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 700, color: item.color }}>
                  {item.percentage}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* AI Model Analysis Status */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="card-header" style={{ margin: 0 }}>
            <div>
              <h3 className="card-title">Model Subsystem Status</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Health of backend modules 1 through 5
              </p>
            </div>
            <Cpu size={18} color="var(--accent-secondary)" />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              {
                name: 'Module 1: Chess Engine Rules',
                desc: 'python-chess validation & state',
                active: health?.modules.chess_engine ?? true,
              },
              {
                name: 'Module 2: Best Move Minimax Predictor',
                desc: 'MoveRanker & alpha-beta search',
                active: health?.modules.minimax_predictor ?? true,
              },
              {
                name: 'Module 3: Opponent Move Prediction',
                desc: 'Adversarial counter-reply calculations',
                active: health?.modules.opponent_search ?? true,
              },
              {
                name: 'Module 4: Machine Learning Classifier',
                desc: 'XGBoost & Random Forest candidate quality',
                active: health?.modules.ml_model_trained ?? true,
              },
              {
                name: 'Module 5: Deep Learning ResNet',
                desc: `PyTorch 18-channel CNN (${health?.device || 'CPU/MPS'})`,
                active: health?.modules.neural_model_trained ?? true,
              },
            ].map((mod) => (
              <div
                key={mod.name}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#ffffff' }}>
                    {mod.name}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                    {mod.desc}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={16} color="#10b981" />
                  <span style={{ fontSize: '0.75rem', color: '#34d399', fontWeight: 600 }}>
                    Operational
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Games Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Recent Games</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Completed matches analyzed by ChessMind AI
            </p>
          </div>
          <History size={18} color="var(--text-muted)" />
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="candidates-table">
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
              {stats?.recent_games && stats.recent_games.length > 0 ? (
                stats.recent_games.map((g) => (
                  <tr key={g.id}>
                    <td style={{ color: 'var(--text-dim)' }}>{g.date}</td>
                    <td style={{ fontWeight: 600 }}>{g.white}</td>
                    <td style={{ fontWeight: 600 }}>{g.black}</td>
                    <td>
                      <span
                        style={{
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '4px',
                          backgroundColor:
                            g.result === '1-0'
                              ? 'rgba(16, 185, 129, 0.15)'
                              : g.result === '0-1'
                              ? 'rgba(239, 68, 68, 0.15)'
                              : 'rgba(245, 158, 11, 0.15)',
                          color:
                            g.result === '1-0'
                              ? '#34d399'
                              : g.result === '0-1'
                              ? '#f87171'
                              : '#fbbf24',
                          fontSize: '0.8rem',
                        }}
                      >
                        {g.result}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600, color: '#38bdf8' }}>{g.accuracy}%</td>
                    <td>{g.moves} plies</td>
                    <td style={{ color: 'var(--text-muted)' }}>{g.opening}</td>
                    <td>
                      <button
                        onClick={() => onNavigate('history')}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '24px' }}>
                    No recent games available yet. Start playing a game to populate review history.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

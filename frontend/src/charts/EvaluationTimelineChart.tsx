import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { GameReviewItem } from '../types';

interface EvaluationTimelineChartProps {
  moves: GameReviewItem[];
  selectedPly?: number;
  onSelectPly?: (ply: number) => void;
  height?: number;
}

export const EvaluationTimelineChart: React.FC<EvaluationTimelineChartProps> = ({
  moves,
  selectedPly,
  onSelectPly,
  height = 200,
}) => {
  if (!moves || moves.length === 0) {
    return (
      <div
        style={{
          height: `${height}px`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-dim)',
          fontSize: '0.85rem',
        }}
      >
        No move evaluation data available to chart.
      </div>
    );
  }

  // Map moves to timeline data points, converting centipawns to pawns clamped between -10 and +10
  const chartData = moves.map((m) => {
    const rawCp = m.played_eval_cp || 0;
    const clampedPawn = Math.max(-10, Math.min(10, rawCp / 100));
    return {
      ply: m.ply,
      moveSan: m.move_san,
      player: m.player,
      evalCp: rawCp,
      evalPawn: Number(clampedPawn.toFixed(2)),
      quality: m.quality,
      loss: m.cp_loss,
      accuracy: m.accuracy,
    };
  });

  return (
    <div style={{ width: '100%', height: `${height}px`, userSelect: 'none' }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 12, right: 12, left: -20, bottom: 0 }}
          onClick={(e: any) => {
            if (e && e.activePayload && e.activePayload.length) {
              const ply = e.activePayload[0].payload.ply;
              onSelectPly?.(ply);
            }
          }}
        >
          <defs>
            <linearGradient id="evalGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.6} />
              <stop offset="50%" stopColor="#6366f1" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0.6} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="ply"
            stroke="var(--text-dim)"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-color)' }}
          />
          <YAxis
            domain={[-8, 8]}
            stroke="var(--text-dim)"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-color)' }}
            tickFormatter={(val) => (val > 0 ? `+${val}` : `${val}`)}
          />
          <ReferenceLine y={0} stroke="rgba(255, 255, 255, 0.2)" strokeDasharray="3 3" />
          {selectedPly !== undefined && (
            <ReferenceLine x={selectedPly} stroke="#fbbf24" strokeWidth={2} />
          )}
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const item = payload[0].payload;
                return (
                  <div
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '8px 12px',
                      boxShadow: 'var(--shadow-md)',
                      fontSize: '0.8rem',
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#ffffff' }}>
                      Ply {item.ply}: {item.player === 'white' ? 'White' : 'Black'} played{' '}
                      <span style={{ color: 'var(--accent-primary)', fontFamily: 'monospace' }}>
                        {item.moveSan}
                      </span>
                    </div>
                    <div style={{ color: item.evalPawn >= 0 ? '#34d399' : '#f87171', marginTop: '2px' }}>
                      Eval: {item.evalPawn >= 0 ? `+${item.evalPawn}` : item.evalPawn} pawns
                    </div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.74rem' }}>
                      Quality: <span style={{ textTransform: 'capitalize' }}>{item.quality}</span> (Loss: {item.loss}cp)
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Area
            type="monotone"
            dataKey="evalPawn"
            stroke="#10b981"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#evalGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

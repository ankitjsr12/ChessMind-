import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface QualityDistributionItem {
  tier: string;
  count: number;
  percentage: number;
  color: string;
}

interface QualityDistributionChartProps {
  data: QualityDistributionItem[];
  height?: number;
}

export const QualityDistributionChart: React.FC<QualityDistributionChartProps> = ({
  data,
  height = 240,
}) => {
  if (!data || data.length === 0) {
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
        No move quality data available yet.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: `${height}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
          <XAxis
            dataKey="tier"
            stroke="var(--text-dim)"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-color)' }}
          />
          <YAxis
            stroke="var(--text-dim)"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-color)' }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const item = payload[0].payload as QualityDistributionItem;
                return (
                  <div
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '8px 12px',
                      boxShadow: 'var(--shadow-md)',
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: '0.85rem', color: item.color }}>
                      {item.tier}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-main)', marginTop: '2px' }}>
                      Moves: <b>{item.count}</b> ({item.percentage}%)
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar dataKey="count" radius={[6, 6, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

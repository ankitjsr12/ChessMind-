import React from 'react';
import type { HealthStatus } from '../types';
import { RefreshCw, Cpu } from 'lucide-react';

interface StatusIndicatorProps {
  health: HealthStatus | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  health,
  loading,
  error,
  onRefresh,
}) => {
  const isHealthy = health?.status === 'healthy';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          borderRadius: '9999px',
          backgroundColor: isHealthy ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          border: `1px solid ${isHealthy ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          fontSize: '0.8rem',
          fontWeight: 600,
          color: isHealthy ? '#34d399' : '#f87171',
        }}
      >
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: isHealthy ? '#10b981' : '#ef4444',
            boxShadow: isHealthy ? '0 0 8px #10b981' : '0 0 8px #ef4444',
          }}
        />
        {loading ? (
          <span>Connecting...</span>
        ) : isHealthy ? (
          <span>Backend Connected</span>
        ) : (
          <span>Backend Offline</span>
        )}
      </div>

      {health?.device && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'rgba(99, 102, 241, 0.12)',
            color: '#a5b4fc',
            fontSize: '0.75rem',
            fontWeight: 500,
          }}
        >
          <Cpu size={14} />
          <span>Device: {health.device.toUpperCase()}</span>
        </div>
      )}

      <button
        onClick={onRefresh}
        title="Check Backend Connection"
        className="btn btn-secondary"
        style={{ padding: '6px 10px', fontSize: '0.8rem' }}
        disabled={loading}
      >
        <RefreshCw size={14} className={loading ? 'spin-icon' : ''} />
      </button>

      {error && !isHealthy && (
        <span style={{ fontSize: '0.75rem', color: '#f87171' }} title={error}>
          {error}
        </span>
      )}
    </div>
  );
};

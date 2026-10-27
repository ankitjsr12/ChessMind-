import React from 'react';
import type { HealthStatus } from '../types';

export type PageId = 'play' | 'analysis' | 'prediction' | 'history' | 'performance';

interface NavigationProps {
  activePage: PageId;
  onPageSelect: (page: PageId) => void;
  health: HealthStatus | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
}

const navItems: Array<{ id: PageId; label: string }> = [
  { id: 'play', label: 'Play Chess' },
  { id: 'analysis', label: 'Game Analysis' },
  { id: 'prediction', label: 'Move Prediction' },
  { id: 'history', label: 'Game History' },
  { id: 'performance', label: 'Model Performance' },
];

export const Navigation: React.FC<NavigationProps> = ({
  activePage,
  onPageSelect,
  health,
  healthLoading,
  onRefreshHealth,
}) => {
  const isHealthy = health?.status === 'healthy';

  return (
    <header className="header">
      <div className="header-container">
        {/* Brand Name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              backgroundColor: '#15803d',
              color: '#ffffff',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: '0.95rem',
            }}
          >
            ♟
          </div>
          <span style={{ fontWeight: 700, fontSize: '1.1rem', color: '#0f172a' }}>
            ChessMind AI
          </span>
          <span className="brand-badge">Engine</span>
        </div>

        {/* Navigation Links */}
        <nav>
          <ul className="nav-menu">
            {navItems.map((item) => {
              const isActive = activePage === item.id;
              return (
                <li key={item.id}>
                  <button
                    className={`nav-link ${isActive ? 'active' : ''}`}
                    onClick={() => onPageSelect(item.id)}
                  >
                    {item.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Backend Status Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={onRefreshHealth}
            title={isHealthy ? 'Connected to backend' : 'Backend is unreachable - click to retry'}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '12px',
              backgroundColor: isHealthy ? '#f0fdf4' : '#fef2f2',
              border: `1px solid ${isHealthy ? '#bbf7d0' : '#fecaca'}`,
              fontSize: '0.78rem',
              fontWeight: 600,
              color: isHealthy ? '#166534' : '#991b1b',
              cursor: 'pointer',
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: isHealthy ? '#16a34a' : '#dc2626',
              }}
            />
            {healthLoading ? 'Checking...' : isHealthy ? 'Connected' : 'Offline'}
          </button>
        </div>
      </div>
    </header>
  );
};

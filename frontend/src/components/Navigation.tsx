import React from 'react';
import type { HealthStatus } from '../types';
import { useAuth } from '../context/AuthContext';

export type PageId = 'play' | 'analysis' | 'prediction' | 'history' | 'performance' | 'my-games';

interface NavigationProps {
  activePage: PageId;
  onPageSelect: (page: PageId) => void;
  health: HealthStatus | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
  onOpenAuth: () => void;
}

const navItems: Array<{ id: PageId; label: string }> = [
  { id: 'play', label: 'Play Chess' },
  { id: 'analysis', label: 'Game Analysis' },
  { id: 'prediction', label: 'Move Prediction' },
  { id: 'my-games', label: 'My Games' },
  { id: 'history', label: 'Game History' },
  { id: 'performance', label: 'Model Performance' },
];

export const Navigation: React.FC<NavigationProps> = ({
  activePage,
  onPageSelect,
  health,
  healthLoading,
  onRefreshHealth,
  onOpenAuth,
}) => {
  const isHealthy = health?.status === 'healthy';
  const { user, profile, signOut, isConfigured } = useAuth();

  const userDisplayName =
    profile?.display_name || user?.user_metadata?.display_name || user?.email?.split('@')[0] || 'User';

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

        {/* Right Status Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Backend Status Pill */}
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
            {healthLoading ? 'Checking...' : isHealthy ? 'Backend Connected' : 'Offline'}
          </button>

          {/* User Auth Controls */}
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 8px',
                  borderRadius: '4px',
                  backgroundColor: 'var(--bg-subtle)',
                  border: '1px solid var(--border-color)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  color: 'var(--text-main)',
                }}
                title={`Signed in as ${user.email}`}
              >
                <span
                  style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--chess-blue)',
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                  }}
                >
                  {userDisplayName.charAt(0).toUpperCase()}
                </span>
                <span style={{ maxWidth: '110px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {userDisplayName}
                </span>
              </div>
              <button
                onClick={() => signOut()}
                className="btn btn-secondary"
                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                title="Sign out of Supabase"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="btn btn-primary"
              style={{ padding: '5px 12px', fontSize: '0.8rem' }}
              title={isConfigured ? 'Sign in or register' : 'Configure Supabase credentials in .env to enable auth'}
            >
              Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

import React, { useState, useEffect, useCallback } from 'react';
import { Navigation } from './components/Navigation';
import type { PageId } from './components/Navigation';
import { PlayPage } from './pages/PlayPage';
import { AnalysisPage } from './pages/AnalysisPage';
import { PredictionPage } from './pages/PredictionPage';
import { HistoryPage } from './pages/HistoryPage';
import { PerformancePage } from './pages/PerformancePage';
import { MyGamesPage } from './pages/MyGamesPage';
import { AuthModal } from './components/AuthModal';
import { AuthProvider } from './context/AuthContext';
import { api } from './services/api';
import type { HealthStatus } from './types';
import type { DbGame } from './types/database';

const MainApp: React.FC = () => {
  const [activePage, setActivePage] = useState<PageId>('play');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Authentication & Game Resume Modal States
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [gameToResume, setGameToResume] = useState<DbGame | null>(null);

  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const data = await api.getHealth();
      if (!data || data.status !== 'healthy' || !data.modules) {
        throw new Error('Backend service returned an unexpected response format.');
      }
      setHealth(data);
      setHealthError(null);
    } catch (err: any) {
      setHealth(null);
      setHealthError(
        err.response?.data?.detail || err.message || 'Cannot reach ChessMind AI backend on port 8000.'
      );
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    // Auto-reconnect poll every 10s
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const handleResumeGame = (game: DbGame) => {
    setGameToResume(game);
    setActivePage('play');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Clean Top Navigation Bar with Supabase Auth Controls */}
      <Navigation
        activePage={activePage}
        onPageSelect={(p) => setActivePage(p)}
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={fetchHealth}
        onOpenAuth={() => setIsAuthModalOpen(true)}
      />

      {/* Main Container */}
      <main className="main-layout" style={{ flex: 1 }}>
        {/* Offline Warning Banner */}
        {healthError && (
          <div
            className="banner-error"
            style={{
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px',
              padding: '12px 16px',
              borderRadius: '8px',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div>
                <b>Python Backend Disconnected:</b> Single-player chess is running in{' '}
                <b>In-Browser Client Engine</b> mode.
              </div>
              <div style={{ fontSize: '0.78rem', color: '#b91c1c' }}>
                Status: {healthError}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                onClick={fetchHealth}
                disabled={healthLoading}
                className="btn btn-secondary"
                style={{
                  fontSize: '0.78rem',
                  padding: '4px 12px',
                  backgroundColor: '#ffffff',
                  color: '#991b1b',
                  borderColor: '#fca5a5',
                  cursor: healthLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {healthLoading ? 'Connecting...' : '↻ Retry Connection'}
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>Start backend:</span>
                <code
                  style={{
                    fontSize: '0.75rem',
                    backgroundColor: '#ffffff',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    border: '1px solid #fca5a5',
                  }}
                >
                  ./start_backend.sh
                </code>
              </div>
            </div>
          </div>
        )}

        {/* Active Page View */}
        {activePage === 'play' && (
          <PlayPage
            key={gameToResume?.id || 'new-game'}
            initialGameToResume={gameToResume}
            onOpenAuth={() => setIsAuthModalOpen(true)}
          />
        )}
        {activePage === 'analysis' && (
          <AnalysisPage onOpenAuth={() => setIsAuthModalOpen(true)} />
        )}
        {activePage === 'prediction' && <PredictionPage />}
        {activePage === 'my-games' && (
          <MyGamesPage
            onResumeGame={handleResumeGame}
            onOpenAuth={() => setIsAuthModalOpen(true)}
          />
        )}
        {activePage === 'history' && <HistoryPage />}
        {activePage === 'performance' && <PerformancePage />}
      </main>

      {/* Supabase Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
      />

      {/* Clean Footer */}
      <footer
        style={{
          borderTop: '1px solid var(--border-color)',
          backgroundColor: 'var(--bg-surface)',
          padding: '16px 20px',
          textAlign: 'center',
          fontSize: '0.78rem',
          color: 'var(--text-muted)',
        }}
      >
        ChessMind AI — Intelligent Chess Move Predictor & Analysis System with Supabase PostgreSQL
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
};

export default App;

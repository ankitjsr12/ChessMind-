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
    setHealthError(null);
    try {
      const data = await api.getHealth();
      setHealth(data);
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
    const interval = setInterval(fetchHealth, 30000);
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
          <div className="banner-error" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <b>Python Backend Disconnected:</b> Single-player chess is running in <b>In-Browser Client Engine</b> mode.
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>To enable deep learning & online 1v1:</span>
              <code style={{ fontSize: '0.75rem', backgroundColor: '#ffffff', padding: '2px 8px', borderRadius: '4px', border: '1px solid #fca5a5' }}>
                ./start_backend.sh
              </code>
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

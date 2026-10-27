import React, { useState, useEffect, useCallback } from 'react';
import { Navigation } from './components/Navigation';
import type { PageId } from './components/Navigation';
import { PlayPage } from './pages/PlayPage';
import { AnalysisPage } from './pages/AnalysisPage';
import { PredictionPage } from './pages/PredictionPage';
import { HistoryPage } from './pages/HistoryPage';
import { PerformancePage } from './pages/PerformancePage';
import { api } from './services/api';
import type { HealthStatus } from './types';

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<PageId>('play');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

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

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Clean Top Navigation Bar */}
      <Navigation
        activePage={activePage}
        onPageSelect={(p) => setActivePage(p)}
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={fetchHealth}
      />

      {/* Main Container */}
      <main className="main-layout" style={{ flex: 1 }}>
        {/* Offline Warning Banner */}
        {healthError && (
          <div className="banner-error" style={{ justifyContent: 'space-between' }}>
            <div>
              <b>Backend Disconnected:</b> {healthError}
            </div>
            <code style={{ fontSize: '0.75rem', backgroundColor: '#ffffff', padding: '2px 6px', borderRadius: '3px' }}>
              uvicorn backend.api.main:app --port 8000
            </code>
          </div>
        )}

        {/* Active Page View */}
        {activePage === 'play' && <PlayPage />}
        {activePage === 'analysis' && <AnalysisPage />}
        {activePage === 'prediction' && <PredictionPage />}
        {activePage === 'history' && <HistoryPage />}
        {activePage === 'performance' && <PerformancePage />}
      </main>

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
        ChessMind AI — Intelligent Chess Move Predictor & Analysis System
      </footer>
    </div>
  );
};

export default App;

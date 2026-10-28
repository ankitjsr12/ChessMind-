import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { SupabaseChessService } from '../services/supabaseChess';
import type { DbGame, DbGameWithDetails } from '../types/database';

interface MyGamesPageProps {
  onResumeGame?: (game: DbGame) => void;
  onOpenAuth?: () => void;
}

export const MyGamesPage: React.FC<MyGamesPageProps> = ({ onResumeGame, onOpenAuth }) => {
  const { user, isConfigured } = useAuth();
  const [games, setGames] = useState<DbGame[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedGameDetails, setSelectedGameDetails] = useState<DbGameWithDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchGames = useCallback(async () => {
    if (!user) {
      setGames([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await SupabaseChessService.listUserGames();
      setGames(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load saved games.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchGames();
  }, [fetchGames]);

  const handleViewDetails = async (gameId: string) => {
    setLoadingDetails(true);
    try {
      const details = await SupabaseChessService.getGameDetails(gameId);
      setSelectedGameDetails(details);
    } catch (err: any) {
      alert(`Could not load game details: ${err.message}`);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleDeleteGame = async (gameId: string, title?: string | null) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${title || 'this game'}"? This action cannot be undone.`
    );
    if (!confirmed) return;

    setDeletingId(gameId);
    try {
      await SupabaseChessService.deleteGame(gameId);
      setGames((prev) => prev.filter((g) => g.id !== gameId));
      if (selectedGameDetails?.id === gameId) {
        setSelectedGameDetails(null);
      }
    } catch (err: any) {
      alert(`Error deleting game: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const getResultBadge = (result: string) => {
    switch (result) {
      case '1-0':
        return <span className="status-badge" style={{ backgroundColor: '#dcfce7', color: '#166534', border: '1px solid #bbf7d0' }}>Won (1-0)</span>;
      case '0-1':
        return <span className="status-badge" style={{ backgroundColor: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' }}>Lost (0-1)</span>;
      case '1/2-1/2':
        return <span className="status-badge" style={{ backgroundColor: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' }}>Draw (½-½)</span>;
      default:
        return <span className="status-badge" style={{ backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>In Progress (*)</span>;
    }
  };

  // Unauthenticated State
  if (!user) {
    return (
      <div style={{ maxWidth: '680px', margin: '40px auto', textAlign: 'center' }}>
        <div className="panel" style={{ padding: '36px 24px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: '#f1f5f9',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto',
              fontSize: '1.5rem',
            }}
          >
            ♟
          </div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px' }}>
            Cloud Saved Games
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '24px', lineHeight: 1.5 }}>
            Sign in to store your chess matches, save move-by-move histories, and access your engine analyses permanently with Supabase PostgreSQL.
          </p>

          {!isConfigured && (
            <div
              style={{
                marginBottom: '20px',
                padding: '12px 16px',
                borderRadius: '6px',
                backgroundColor: '#fffbeb',
                border: '1px solid #fef3c7',
                fontSize: '0.82rem',
                color: '#92400e',
                textAlign: 'left',
              }}
            >
              <b>Supabase setup needed:</b> Set <code>VITE_SUPABASE_URL</code> and{' '}
              <code>VITE_SUPABASE_ANON_KEY</code> in <code>frontend/.env</code> to activate cloud database integration.
            </div>
          )}

          <button
            onClick={onOpenAuth}
            disabled={!isConfigured}
            className="btn btn-primary"
            style={{ padding: '8px 20px', fontSize: '0.9rem' }}
          >
            Sign In or Register
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">My Saved Games</h1>
          <p className="page-description">
            Your permanent cloud game library, backed by Supabase PostgreSQL with Row Level Security.
          </p>
        </div>
        <button
          onClick={fetchGames}
          disabled={loading}
          className="btn btn-secondary"
          style={{ fontSize: '0.82rem', padding: '6px 12px' }}
        >
          {loading ? 'Refreshing...' : '↻ Refresh Games'}
        </button>
      </div>

      {error && (
        <div className="banner-error" style={{ marginBottom: '16px' }}>
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Main Content Area */}
      <div style={{ display: 'grid', gridTemplateColumns: selectedGameDetails ? '1fr 1fr' : '1fr', gap: '24px' }}>
        {/* Games Table Panel */}
        <div className="panel" style={{ overflow: 'hidden' }}>
          <div className="panel-header">
            <span className="panel-title">Saved Matches</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {games.length} total saved
            </span>
          </div>

          {loading && games.length === 0 ? (
            <div style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading your saved games from Supabase...
            </div>
          ) : games.length === 0 ? (
            <div style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '2rem', marginBottom: '8px' }}>📂</div>
              <p style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
                No saved games yet
              </p>
              <p style={{ fontSize: '0.82rem' }}>
                Start a game on the "Play Chess" tab and click <b>Save to Cloud</b> to record your match permanently!
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Game Title / Opponent</th>
                    <th>Color</th>
                    <th>Result</th>
                    <th>Date Saved</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {games.map((g) => {
                    const isSelected = selectedGameDetails?.id === g.id;
                    return (
                      <tr
                        key={g.id}
                        style={{
                          backgroundColor: isSelected ? 'var(--chess-blue-light)' : undefined,
                        }}
                      >
                        <td>
                          <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                            {g.title || `Game vs ${g.opponent_type}`}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            Opponent: {g.opponent_type}
                          </div>
                        </td>
                        <td>
                          <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>
                            {g.player_colour === 'white' ? '⚪ White' : '⚫ Black'}
                          </span>
                        </td>
                        <td>{getResultBadge(g.result)}</td>
                        <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          {new Date(g.created_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              onClick={() => handleViewDetails(g.id)}
                              disabled={loadingDetails}
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                              title="Inspect moves and analysis"
                            >
                              Details
                            </button>
                            {onResumeGame && (
                              <button
                                onClick={() => onResumeGame(g)}
                                className="btn btn-primary"
                                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                title="Resume this match on Play Chess board"
                              >
                                Resume
                              </button>
                            )}
                            <button
                              onClick={() => handleDeleteGame(g.id, g.title)}
                              disabled={deletingId === g.id}
                              className="btn btn-secondary"
                              style={{
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                color: 'var(--chess-red)',
                                borderColor: '#fecaca',
                              }}
                              title="Delete game from Supabase"
                            >
                              {deletingId === g.id ? '...' : 'Delete'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Selected Game Details Panel */}
        {selectedGameDetails && (
          <div className="panel" style={{ height: 'fit-content' }}>
            <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span className="panel-title">
                  {selectedGameDetails.title || 'Game Details'}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '8px' }}>
                  ({selectedGameDetails.moves?.length || 0} moves recorded)
                </span>
              </div>
              <button
                onClick={() => setSelectedGameDetails(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '1rem',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: '16px' }}>
              {/* Metadata Badges */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
                {getResultBadge(selectedGameDetails.result)}
                <span className="status-badge" style={{ backgroundColor: '#f1f5f9', border: '1px solid #e2e8f0' }}>
                  Side: {selectedGameDetails.player_colour}
                </span>
                <span className="status-badge" style={{ backgroundColor: '#f1f5f9', border: '1px solid #e2e8f0' }}>
                  Opponent: {selectedGameDetails.opponent_type}
                </span>
              </div>

              {/* FEN */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Current Position (FEN)
                </div>
                <code
                  style={{
                    display: 'block',
                    padding: '8px 10px',
                    backgroundColor: 'var(--bg-subtle)',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    wordBreak: 'break-all',
                  }}
                >
                  {selectedGameDetails.current_fen}
                </code>
              </div>

              {/* Recorded Moves Sequence */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                  Move History ({selectedGameDetails.moves?.length || 0} plies)
                </div>
                {selectedGameDetails.moves && selectedGameDetails.moves.length > 0 ? (
                  <div
                    style={{
                      maxHeight: '160px',
                      overflowY: 'auto',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      padding: '8px 12px',
                      backgroundColor: 'var(--bg-surface)',
                      fontSize: '0.82rem',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    {selectedGameDetails.moves.map((m, idx) => (
                      <span key={m.id || idx} style={{ display: 'inline-flex', gap: '2px' }}>
                        {idx % 2 === 0 && (
                          <span style={{ color: 'var(--text-dim)', fontWeight: 600 }}>
                            {Math.floor(idx / 2) + 1}.
                          </span>
                        )}
                        <span style={{ fontWeight: 500, color: 'var(--text-main)' }}>{m.san}</span>
                      </span>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    No individual moves were recorded for this game.
                  </div>
                )}
              </div>

              {/* Saved Analysis (if present) */}
              {selectedGameDetails.analysis && selectedGameDetails.analysis.length > 0 && (
                <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                    Saved Analysis Records ({selectedGameDetails.analysis.length})
                  </div>
                  {selectedGameDetails.analysis.map((a) => (
                    <div
                      key={a.id}
                      style={{
                        padding: '8px 10px',
                        backgroundColor: 'var(--bg-subtle)',
                        borderRadius: '4px',
                        fontSize: '0.78rem',
                        marginBottom: '6px',
                      }}
                    >
                      <div>
                        <b>Best Move:</b> {a.best_move} · <b>Evaluation:</b> {a.evaluation_score} · <b>Depth:</b> {a.search_depth}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Actions Footer */}
              <div style={{ marginTop: '20px', display: 'flex', gap: '8px' }}>
                {onResumeGame && (
                  <button
                    onClick={() => onResumeGame(selectedGameDetails)}
                    className="btn btn-primary"
                    style={{ flex: 1, justifyContent: 'center' }}
                  >
                    Resume Game in Play Mode
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

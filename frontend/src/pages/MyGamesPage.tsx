import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { SupabaseChessService } from '../services/supabaseChess';
import type { DbGame, DbGameWithDetails } from '../types/database';

interface MyGamesPageProps {
  onResumeGame?: (game: DbGame) => void;
  onOpenAuth?: () => void;
}

export const MyGamesPage: React.FC<MyGamesPageProps> = ({ onResumeGame, onOpenAuth }) => {
  const { user, isConfigured, connectionStatus, refreshConnection } = useAuth();
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
      setError(err.message || 'Failed to load saved games from Supabase.');
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

  const renderStatusBadge = () => {
    switch (connectionStatus) {
      case 'connected':
        return (
          <span className="status-badge" style={{ backgroundColor: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0', fontSize: '0.72rem' }}>
            ☁️ Connected: Supabase Cloud
          </span>
        );
      case 'syncing':
        return (
          <span className="status-badge" style={{ backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe', fontSize: '0.72rem' }}>
            🔄 Syncing: Synchronizing data
          </span>
        );
      case 'not_configured':
        return (
          <span className="status-badge" style={{ backgroundColor: '#fff7ed', color: '#9a3412', border: '1px solid #fed7aa', fontSize: '0.72rem' }}>
            ⚠️ Not Configured: Supabase credentials missing
          </span>
        );
      case 'disconnected':
      default:
        return (
          <span className="status-badge" style={{ backgroundColor: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca', fontSize: '0.72rem' }}>
            ⚠️ Disconnected: Cloud connection unavailable
          </span>
        );
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
          <div style={{ display: 'inline-block', marginBottom: '12px' }}>
            {renderStatusBadge()}
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
                backgroundColor: '#fff7ed',
                border: '1px solid #fed7aa',
                fontSize: '0.82rem',
                color: '#9a3412',
                textAlign: 'left',
              }}
            >
              <b>Not Configured:</b> Supabase credentials missing.
              To connect your database, add <code>VITE_SUPABASE_URL</code> and{' '}
              <code>VITE_SUPABASE_ANON_KEY</code> to <code>frontend/.env</code> (or to Vercel Environment Variables in production).
            </div>
          )}

          <button
            onClick={onOpenAuth}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 className="page-title" style={{ margin: 0 }}>My Saved Games</h1>
            {renderStatusBadge()}
          </div>
          <p className="page-description">
            Your saved game library with full move histories and engine analyses stored in Supabase PostgreSQL.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => {
              refreshConnection();
              fetchGames();
            }}
            disabled={loading}
            className="btn btn-secondary"
            style={{ fontSize: '0.82rem', padding: '6px 12px' }}
          >
            {loading ? 'Refreshing...' : '↻ Refresh Games'}
          </button>
        </div>
      </div>

      {error && (
        <div className="banner-error" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {error}</span>
          <button
            onClick={fetchGames}
            style={{
              background: 'none',
              border: 'none',
              color: '#991b1b',
              fontWeight: 600,
              textDecoration: 'underline',
              cursor: 'pointer',
              fontSize: '0.8rem',
            }}
          >
            Retry Sync
          </button>
        </div>
      )}

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: selectedGameDetails ? '1fr 1fr' : '1fr', gap: '24px' }}>
        {/* Games Table List */}
        <div className="panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0 }}>
              Matches ({games.length})
            </h2>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Logged in as: <b>{user.email}</b>
            </span>
          </div>

          {loading && games.length === 0 ? (
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading matches from Supabase PostgreSQL...
            </div>
          ) : games.length === 0 ? (
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
              <p style={{ margin: '0 0 12px 0' }}>No saved games found in Supabase cloud database.</p>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)', margin: 0 }}>
                Play a game in the <b>Play Chess</b> tab and click <b>Save Match to Cloud</b> to store games permanently!
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '10px 8px' }}>Title</th>
                    <th style={{ padding: '10px 8px' }}>Opponent</th>
                    <th style={{ padding: '10px 8px' }}>Colour</th>
                    <th style={{ padding: '10px 8px' }}>Result</th>
                    <th style={{ padding: '10px 8px' }}>Saved At</th>
                    <th style={{ padding: '10px 8px', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {games.map((game) => {
                    const isSelected = selectedGameDetails?.id === game.id;
                    const dateFormatted = new Date(game.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    });

                    return (
                      <tr
                        key={game.id}
                        style={{
                          borderBottom: '1px solid var(--border-color)',
                          backgroundColor: isSelected ? 'var(--bg-subtle)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '12px 8px', fontWeight: 600 }}>
                          {game.title || 'Untitled Match'}
                        </td>
                        <td style={{ padding: '12px 8px', textTransform: 'capitalize' }}>
                          {game.opponent_type}
                        </td>
                        <td style={{ padding: '12px 8px' }}>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              textTransform: 'capitalize',
                            }}
                          >
                            <span
                              style={{
                                width: '10px',
                                height: '10px',
                                borderRadius: '50%',
                                backgroundColor: game.player_colour === 'white' ? '#ffffff' : '#000000',
                                border: '1px solid #94a3b8',
                              }}
                            />
                            {game.player_colour}
                          </span>
                        </td>
                        <td style={{ padding: '12px 8px' }}>
                          {getResultBadge(game.result)}
                        </td>
                        <td style={{ padding: '12px 8px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                          {dateFormatted}
                        </td>
                        <td style={{ padding: '12px 8px', textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              onClick={() => handleViewDetails(game.id)}
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '0.75rem' }}
                              title="Inspect moves and engine evaluations"
                            >
                              Inspect
                            </button>
                            {onResumeGame && (
                              <button
                                onClick={() => onResumeGame(game)}
                                className="btn btn-primary"
                                style={{ padding: '3px 8px', fontSize: '0.75rem' }}
                                title="Resume match on Play board"
                              >
                                Resume
                              </button>
                            )}
                            <button
                              onClick={() => handleDeleteGame(game.id, game.title)}
                              disabled={deletingId === game.id}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#ef4444',
                                cursor: 'pointer',
                                padding: '3px 6px',
                                fontSize: '0.75rem',
                              }}
                              title="Delete permanently from Supabase"
                            >
                              {deletingId === game.id ? '...' : '✕'}
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
          <div className="panel" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0 }}>
                Match Details: {selectedGameDetails.title || 'Selected Match'}
              </h2>
              <button
                onClick={() => setSelectedGameDetails(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                ✕
              </button>
            </div>

            {loadingDetails ? (
              <div style={{ padding: '30px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
                Loading game moves & analysis...
              </div>
            ) : (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '16px' }}>
                  <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>RESULT</div>
                    <div style={{ fontWeight: 600, marginTop: '2px' }}>{selectedGameDetails.result}</div>
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>MOVES RECORDED</div>
                    <div style={{ fontWeight: 600, marginTop: '2px' }}>{selectedGameDetails.moves?.length || 0}</div>
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: '4px' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>ANALYSES</div>
                    <div style={{ fontWeight: 600, marginTop: '2px' }}>{selectedGameDetails.analysis?.length || 0}</div>
                  </div>
                </div>

                {/* Move List */}
                <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '8px' }}>
                  Move History ({selectedGameDetails.moves?.length || 0} plies)
                </h3>
                <div
                  style={{
                    maxHeight: '160px',
                    overflowY: 'auto',
                    border: '1px solid var(--border-color)',
                    borderRadius: '4px',
                    padding: '8px',
                    marginBottom: '16px',
                    fontSize: '0.8rem',
                    fontFamily: 'monospace',
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '6px',
                  }}
                >
                  {selectedGameDetails.moves && selectedGameDetails.moves.length > 0 ? (
                    selectedGameDetails.moves.map((m) => (
                      <span
                        key={m.id}
                        style={{
                          padding: '2px 6px',
                          backgroundColor: 'var(--bg-subtle)',
                          borderRadius: '3px',
                        }}
                      >
                        {m.move_number}. <b>{m.san}</b>
                      </span>
                    ))
                  ) : (
                    <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
                      No moves recorded for this game.
                    </span>
                  )}
                </div>

                {/* Engine Analysis Records */}
                {selectedGameDetails.analysis && selectedGameDetails.analysis.length > 0 && (
                  <div>
                    <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '8px' }}>
                      Stored Engine Evaluations
                    </h3>
                    <div style={{ maxHeight: '160px', overflowY: 'auto' }}>
                      {selectedGameDetails.analysis.map((a) => (
                        <div
                          key={a.id}
                          style={{
                            padding: '8px',
                            border: '1px solid var(--border-color)',
                            borderRadius: '4px',
                            marginBottom: '6px',
                            fontSize: '0.78rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                            <span>Best Move: <b>{a.best_move}</b></span>
                            <span>Eval: {a.evaluation_score >= 0 ? `+${a.evaluation_score}` : a.evaluation_score}</span>
                          </div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: '2px' }}>
                            Depth: {a.search_depth} | {new Date(a.created_at).toLocaleTimeString()}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Current FEN */}
                <div style={{ marginTop: '14px' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    CURRENT FEN
                  </div>
                  <input
                    type="text"
                    readOnly
                    value={selectedGameDetails.current_fen}
                    className="input-text"
                    style={{ width: '100%', fontSize: '0.75rem', fontFamily: 'monospace' }}
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

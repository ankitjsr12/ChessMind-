import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Chessboard } from 'react-chessboard';
import { api } from '../services/api';
import type { GameReviewReport, GameReviewItem, QualityTier, ImportedOnlineGame } from '../types';
import { EvaluationTimelineChart } from '../charts/EvaluationTimelineChart';
import {
  FileSearch,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
  Award,
  BookOpen,
  Info,
  Upload,
  Globe,
  Sparkles,
  ShieldAlert,
} from 'lucide-react';

const SAMPLE_GAMES: Record<string, { title: string; moves: string[] }> = {
  opera: {
    title: 'Morphy vs Duke Karl (Opera Game)',
    moves: [
      'e4', 'e5', 'Nf3', 'd6', 'd4', 'Bg4', 'dxe5', 'Bxf3', 'Qxf3', 'dxe5',
      'Bc4', 'Nf6', 'Qb3', 'Qe7', 'Nc3', 'c6', 'Bg5', 'b5', 'Nxb5', 'cxb5',
      'Bxb5+', 'Nbd7', 'O-O-O', 'Rd8', 'Rxd7', 'Rxd7', 'Rd1', 'Qe6', 'Bxd7+', 'Nxd7',
      'Qb8+', 'Nxb8', 'Rd8#'
    ],
  },
  italian: {
    title: 'Italian Game Classic Line',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5', 'c3', 'Nf6', 'd4', 'exd4', 'cxd4', 'Bb4+'],
  },
  ruy_lopez: {
    title: 'Ruy Lopez: Morphy Defense',
    moves: ['e4', 'e5', 'Nf3', 'Nc6', 'Bb5', 'a6', 'Ba4', 'Nf6', 'O-O', 'Be7', 'Re1', 'b5', 'Bb3', 'd6'],
  },
};

const getTierBadge = (quality: QualityTier | 'best') => {
  switch (quality) {
    case 'brilliant':
      return (
        <span className="badge" style={{ backgroundColor: 'rgba(6, 182, 212, 0.25)', color: '#22d3ee', border: '1px solid #06b6d4', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Sparkles size={12} /> Brilliant (!!)
        </span>
      );
    case 'best':
    case 'excellent':
      return <span className="badge badge-excellent">⭐ Best</span>;
    case 'good':
      return <span className="badge badge-good">Good</span>;
    case 'inaccuracy':
      return <span className="badge badge-inaccuracy">?! Inaccuracy</span>;
    case 'mistake':
      return <span className="badge badge-mistake">? Mistake</span>;
    case 'blunder':
      return <span className="badge badge-blunder">?? Blunder</span>;
    case 'missed_win':
      return (
        <span className="badge" style={{ backgroundColor: 'rgba(168, 85, 247, 0.25)', color: '#c084fc', border: '1px solid #a855f7' }}>
          Missed Win
        </span>
      );
    default:
      return <span className="badge badge-good">{quality}</span>;
  }
};

export const ReviewPage: React.FC = () => {
  // Input Mode: 'preset' | 'pgn' | 'online'
  const [activeTab, setActiveTab] = useState<'preset' | 'pgn' | 'online'>('preset');
  const [selectedGameKey, setSelectedGameKey] = useState<string>('opera');

  // Custom PGN Input
  const [pgnText, setPgnText] = useState<string>('');

  // Online Platform Fetch
  const [platform, setPlatform] = useState<'lichess' | 'chesscom'>('lichess');
  const [onlineUsername, setOnlineUsername] = useState<string>('');
  const [fetchedGames, setFetchedGames] = useState<ImportedOnlineGame[]>([]);
  const [isFetchingOnline, setIsFetchingOnline] = useState<boolean>(false);

  // Report & Review State
  const [report, setReport] = useState<GameReviewReport | null>(null);
  const [gameInfo, setGameInfo] = useState<any>(null);
  const [currentPlyIndex, setCurrentPlyIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Trigger game review analysis for move list
  const analyzeGame = useCallback(async (moves: string[], initialFen?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.reviewGame(moves, initialFen);
      setReport(data);
      setCurrentPlyIndex(data.moves.length > 0 ? 0 : 0);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to review game.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Trigger review via raw PGN
  const handleAnalyzePgn = useCallback(async (rawPgn: string) => {
    if (!rawPgn.trim()) {
      setError('Please enter or upload valid PGN text.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.reviewPgn(rawPgn);
      setGameInfo(res.game_info);
      setReport(res.review);
      setCurrentPlyIndex(res.review.moves.length > 0 ? 0 : 0);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to parse and analyze PGN.');
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        if (content) {
          setPgnText(content);
          handleAnalyzePgn(content);
        }
      };
      reader.readAsText(file);
    }
  };

  // Fetch online games
  const handleFetchOnline = async () => {
    if (!onlineUsername.trim()) return;
    setIsFetchingOnline(true);
    setError(null);
    setFetchedGames([]);
    try {
      if (platform === 'lichess') {
        const res = await api.importLichess(onlineUsername.trim(), 5);
        setFetchedGames(res.games || []);
      } else {
        const res = await api.importChessCom(onlineUsername.trim(), 5);
        setFetchedGames(res.games || []);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || `Failed to fetch ${platform} games.`);
    } finally {
      setIsFetchingOnline(false);
    }
  };

  // Run on mount or preset game select
  useEffect(() => {
    if (activeTab === 'preset') {
      const game = SAMPLE_GAMES[selectedGameKey];
      if (game) {
        setGameInfo(null);
        analyzeGame(game.moves);
      }
    }
  }, [activeTab, selectedGameKey, analyzeGame]);

  // Keyboard navigation for moves (Left/Right arrows)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!report || report.moves.length === 0) return;
      if (e.key === 'ArrowLeft') {
        setCurrentPlyIndex((idx) => Math.max(0, idx - 1));
      } else if (e.key === 'ArrowRight') {
        setCurrentPlyIndex((idx) => Math.min(report.moves.length - 1, idx + 1));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [report]);

  const currentMove: GameReviewItem | undefined = report?.moves[currentPlyIndex];
  const currentFen = currentMove?.fen_after || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  // Count blunders, mistakes, brilliancies
  const qualityStats = useMemo(() => {
    if (!report) return { mistakes: 0, blunders: 0, brilliant: 0, missedWins: 0 };
    let mistakes = 0;
    let blunders = 0;
    let brilliant = 0;
    let missedWins = 0;
    for (const m of report.moves) {
      if (m.quality === 'blunder') blunders++;
      if (m.quality === 'mistake') mistakes++;
      if (m.quality === 'brilliant') brilliant++;
      if (m.quality === 'missed_win') missedWins++;
    }
    return { mistakes, blunders, brilliant, missedWins };
  }, [report]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner & Mode Tabs */}
      <div className="card" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                backgroundColor: 'rgba(6, 182, 212, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <FileSearch size={24} color="#06b6d4" />
            </div>
            <div>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
                Game Accuracy & Blunder Review
              </h2>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Senior Engine Review with ECO Opening Classification & Tactical Diagnostics
              </div>
            </div>
          </div>

          {/* Navigation Mode Tabs */}
          <div style={{ display: 'flex', gap: '8px', backgroundColor: 'rgba(255, 255, 255, 0.04)', padding: '4px', borderRadius: 'var(--radius-sm)' }}>
            <button
              onClick={() => setActiveTab('preset')}
              className={`btn ${activeTab === 'preset' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.82rem', padding: '6px 14px' }}
            >
              <BookOpen size={14} style={{ marginRight: '6px' }} />
              Preset Games
            </button>
            <button
              onClick={() => setActiveTab('pgn')}
              className={`btn ${activeTab === 'pgn' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.82rem', padding: '6px 14px' }}
            >
              <Upload size={14} style={{ marginRight: '6px' }} />
              Import PGN
            </button>
            <button
              onClick={() => setActiveTab('online')}
              className={`btn ${activeTab === 'online' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.82rem', padding: '6px 14px' }}
            >
              <Globe size={14} style={{ marginRight: '6px' }} />
              Lichess / Chess.com
            </button>
          </div>
        </div>

        {/* Tab 1: Preset selector */}
        {activeTab === 'preset' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>
              Select Historic Match:
            </span>
            <select
              value={selectedGameKey}
              onChange={(e) => setSelectedGameKey(e.target.value)}
              disabled={loading}
              style={{
                backgroundColor: 'var(--bg-main)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '8px 14px',
                fontSize: '0.88rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {Object.entries(SAMPLE_GAMES).map(([key, item]) => (
                <option key={key} value={key}>
                  {item.title} ({item.moves.length} moves)
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Tab 2: Custom PGN Import */}
        {activeTab === 'pgn' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Paste any standard PGN text or choose a .pgn file from your device:
              </span>
              <label className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '6px 12px', cursor: 'pointer' }}>
                <Upload size={14} style={{ marginRight: '6px' }} />
                Upload .pgn File
                <input type="file" accept=".pgn" onChange={handleFileUpload} style={{ display: 'none' }} />
              </label>
            </div>
            <textarea
              value={pgnText}
              onChange={(e) => setPgnText(e.target.value)}
              placeholder={`[Event "World Championship"]\n[White "Carlsen, Magnus"]\n[Black "Caruana, Fabiano"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6...`}
              rows={4}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-main)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '10px 14px',
                fontFamily: 'monospace',
                fontSize: '0.82rem',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => handleAnalyzePgn(pgnText)}
                disabled={loading || !pgnText.trim()}
                className="btn btn-primary"
                style={{ fontSize: '0.85rem', padding: '8px 18px' }}
              >
                {loading ? 'Analyzing PGN...' : 'Analyze Full PGN Game'}
              </button>
            </div>
          </div>
        )}

        {/* Tab 3: Online Profile Importer */}
        {activeTab === 'online' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value as any)}
                style={{
                  backgroundColor: 'var(--bg-main)',
                  color: 'var(--text-main)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                }}
              >
                <option value="lichess">Lichess.org</option>
                <option value="chesscom">Chess.com</option>
              </select>

              <input
                type="text"
                value={onlineUsername}
                onChange={(e) => setOnlineUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleFetchOnline()}
                placeholder={`Enter ${platform === 'lichess' ? 'Lichess' : 'Chess.com'} username (e.g. MagnusCarlsen)`}
                style={{
                  flex: 1,
                  minWidth: '220px',
                  backgroundColor: 'var(--bg-main)',
                  color: 'var(--text-main)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                }}
              />

              <button
                onClick={handleFetchOnline}
                disabled={isFetchingOnline || !onlineUsername.trim()}
                className="btn btn-primary"
                style={{ fontSize: '0.85rem', padding: '8px 18px' }}
              >
                {isFetchingOnline ? 'Fetching...' : 'Fetch Recent Matches'}
              </button>
            </div>

            {/* List of fetched online matches */}
            {fetchedGames.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
                {fetchedGames.map((g, idx) => (
                  <div
                    key={g.id || idx}
                    onClick={() => {
                      setGameInfo({
                        white: g.white,
                        black: g.black,
                        white_elo: g.white_elo,
                        black_elo: g.black_elo,
                        result: g.result,
                        event: `${platform.toUpperCase()} ${g.speed || 'Match'}`,
                        date: new Date().toLocaleDateString(),
                      });
                      analyzeGame(g.moves_san);
                    }}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-color)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-primary)')}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38bdf8' }}>
                        {g.ply_count} moves
                      </span>
                      <span className="badge" style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', fontSize: '0.72rem' }}>
                        {g.result}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.84rem', fontWeight: 600, color: '#fff' }}>
                      {g.white} ({g.white_elo}) vs {g.black} ({g.black_elo})
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#fca5a5',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertTriangle size={18} color="#ef4444" />
          <span>{error}</span>
        </div>
      )}

      {/* Game Details Banner (If PGN metadata or online game selected) */}
      {(gameInfo || report) && (
        <div
          className="card"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
            padding: '12px 20px',
            backgroundColor: 'rgba(30, 41, 59, 0.5)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontWeight: 800, color: '#fff', fontSize: '0.95rem' }}>
              {gameInfo ? `${gameInfo.white} (${gameInfo.white_elo}) vs ${gameInfo.black} (${gameInfo.black_elo})` : 'Analysis Match'}
            </span>
            {gameInfo?.result && (
              <span className="badge" style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)' }}>
                {gameInfo.result}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {report?.eco && (
              <span className="badge" style={{ backgroundColor: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', fontWeight: 800 }}>
                {report.eco}
              </span>
            )}
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#38bdf8' }}>
              {report?.opening || 'Detecting Opening...'}
            </span>
          </div>
        </div>
      )}

      {/* Accuracy & Tactical KPI Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">White Accuracy</span>
          <div className="stat-value" style={{ color: '#34d399' }}>
            {report ? `${report.white_accuracy}%` : '...'}
          </div>
          <div className="stat-subtext">Senior loss model</div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Black Accuracy</span>
          <div className="stat-value" style={{ color: '#60a5fa' }}>
            {report ? `${report.black_accuracy}%` : '...'}
          </div>
          <div className="stat-subtext">Senior loss model</div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Tactical Blunders</span>
          <div className="stat-value" style={{ color: qualityStats.blunders > 0 ? '#f87171' : '#34d399' }}>
            {qualityStats.blunders}
          </div>
          <div className="stat-subtext">{qualityStats.mistakes} mistakes detected</div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Brilliant Moves</span>
          <div className="stat-value" style={{ color: '#22d3ee' }}>
            {qualityStats.brilliant}
          </div>
          <div className="stat-subtext">Critical sacrifices</div>
        </div>
      </div>

      {/* Interactive Evaluation Timeline */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <h3 className="card-title">Centipawn Evaluation Advantage by Move</h3>
        <EvaluationTimelineChart
          moves={report?.moves || []}
          selectedPly={currentPlyIndex}
          onSelectPly={(ply) => setCurrentPlyIndex(ply)}
        />
      </div>

      {/* Two Column Layout: Board & Move Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Left Column: Board & Controls */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}>
          <div style={{ width: '100%', maxWidth: '440px', aspectRatio: '1/1' }}>
            <Chessboard
              options={{
                position: currentFen,
                boardOrientation: 'white',
                darkSquareStyle: { backgroundColor: '#769656' },
                lightSquareStyle: { backgroundColor: '#eeeed2' },
              }}
            />
          </div>

          {/* Stepper Controls */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', width: '100%', maxWidth: '440px' }}>
            <button
              className="btn btn-secondary"
              onClick={() => setCurrentPlyIndex(0)}
              disabled={currentPlyIndex === 0 || loading}
              style={{ flex: 1, padding: '8px' }}
              title="First move"
            >
              <ChevronsLeft size={16} />
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setCurrentPlyIndex((idx) => Math.max(0, idx - 1))}
              disabled={currentPlyIndex === 0 || loading}
              style={{ flex: 1, padding: '8px' }}
              title="Previous move (Left Arrow)"
            >
              <ChevronLeft size={16} />
            </button>

            <span style={{ fontSize: '0.85rem', fontWeight: 700, minWidth: '90px', textAlign: 'center', color: '#fff' }}>
              {report?.moves.length ? `Ply ${currentPlyIndex + 1} / ${report.moves.length}` : '0 / 0'}
            </span>

            <button
              className="btn btn-secondary"
              onClick={() => setCurrentPlyIndex((idx) => Math.min((report?.moves.length || 1) - 1, idx + 1))}
              disabled={!report || currentPlyIndex >= report.moves.length - 1 || loading}
              style={{ flex: 1, padding: '8px' }}
              title="Next move (Right Arrow)"
            >
              <ChevronRight size={16} />
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setCurrentPlyIndex((report?.moves.length || 1) - 1)}
              disabled={!report || currentPlyIndex >= report.moves.length - 1 || loading}
              style={{ flex: 1, padding: '8px' }}
              title="Last move"
            >
              <ChevronsRight size={16} />
            </button>
          </div>
        </div>

        {/* Right Column: Move Details & Explainable Tactical Reason */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {currentMove && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="card-header" style={{ margin: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Award size={18} color="var(--accent-primary)" />
                  <h3 className="card-title">Ply {currentMove.ply} Move Analysis</h3>
                </div>
                {getTierBadge(currentMove.quality)}
              </div>

              {/* Explainable Tactical Insight Card */}
              {currentMove.explanation && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: currentMove.quality === 'blunder' ? 'rgba(239, 68, 68, 0.12)' : currentMove.quality === 'brilliant' ? 'rgba(6, 182, 212, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                    border: `1px solid ${currentMove.quality === 'blunder' ? 'rgba(239, 68, 68, 0.3)' : currentMove.quality === 'brilliant' ? 'rgba(6, 182, 212, 0.3)' : 'var(--border-color)'}`,
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                  }}
                >
                  {currentMove.quality === 'blunder' ? (
                    <ShieldAlert size={18} color="#ef4444" style={{ marginTop: '2px', flexShrink: 0 }} />
                  ) : currentMove.quality === 'brilliant' ? (
                    <Sparkles size={18} color="#06b6d4" style={{ marginTop: '2px', flexShrink: 0 }} />
                  ) : (
                    <Info size={18} color="#38bdf8" style={{ marginTop: '2px', flexShrink: 0 }} />
                  )}
                  <div>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#fff', marginBottom: '2px' }}>
                      Tactical Diagnostic:
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-main)', lineHeight: 1.4 }}>
                      {currentMove.explanation}
                    </div>
                  </div>
                </div>
              )}

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  padding: '14px',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Played Move</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '1.25rem', fontWeight: 800, color: '#ffffff' }}>
                    {currentMove.move_san}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Player: {currentMove.player.toUpperCase()}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Engine Recommended Move</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '1.25rem', fontWeight: 800, color: '#34d399' }}>
                    {currentMove.best_move_san}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: currentMove.cp_loss > 0 ? '#f87171' : '#34d399' }}>
                    Loss: {currentMove.cp_loss} cp
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Calculated Accuracy:</span>
                <span style={{ fontWeight: 800, color: '#38bdf8' }}>{currentMove.accuracy}%</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Post-Move Position Eval:</span>
                <span style={{ fontWeight: 700 }}>
                  {currentMove.played_eval_cp > 0 ? `+${(currentMove.played_eval_cp / 100).toFixed(2)}` : (currentMove.played_eval_cp / 100).toFixed(2)} pawns
                </span>
              </div>
            </div>
          )}

          {/* Documented Accuracy Formula Card */}
          <div
            className="card"
            style={{
              backgroundColor: 'rgba(99, 102, 241, 0.05)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Info size={16} color="#818cf8" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#c7d2fe' }}>
                Documented Accuracy Formula & Tiers
              </span>
            </div>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '8px' }}>
              Accuracy evaluates each move relative to the best engine alternative using an exponential loss decay:
            </p>
            <code
              style={{
                display: 'block',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(0, 0, 0, 0.4)',
                fontSize: '0.78rem',
                color: '#34d399',
                fontFamily: 'monospace',
              }}
            >
              Accuracy = clamp(103.1668 · exp(-0.04354 · Δcp) - 3.1669, 0, 100)
            </code>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: '8px' }}>
              Brilliant moves reward winning tactical sacrifices. Blunders exceeding 300 centipawns exponentially decay to 0%.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

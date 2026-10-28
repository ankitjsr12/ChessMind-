import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Chess } from 'chess.js';
import type { Square } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import type { Arrow } from 'react-chessboard';
import { api } from '../services/api';
import type { CandidateMove } from '../types';
import { EvaluationBar } from '../components/EvaluationBar';
import { CandidateMovesList } from '../components/CandidateMovesList';
import { ExplainableAIPanel } from '../components/ExplainableAIPanel';
import { useAuth } from '../context/AuthContext';
import { SupabaseChessService } from '../services/supabaseChess';

interface AnalysisPageProps {
  onOpenAuth?: () => void;
}

export const AnalysisPage: React.FC<AnalysisPageProps> = ({ onOpenAuth }) => {
  const { user } = useAuth();
  const [game, setGame] = useState<Chess>(new Chess());
  const [fenInput, setFenInput] = useState<string>(new Chess().fen());
  const [orientation, setOrientation] = useState<'white' | 'black'>('white');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [bestMove, setBestMove] = useState<{ san: string; uci: string } | null>(null);
  const [scoreCentipawns, setScoreCentipawns] = useState<number>(0);
  const [evaluationText, setEvaluationText] = useState<string>('+0.0');
  const [candidates, setCandidates] = useState<CandidateMove[]>([]);
  const [tacticalThreat, setTacticalThreat] = useState<string | undefined>();
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateMove | null>(null);

  const [isSavingAnalysis, setIsSavingAnalysis] = useState<boolean>(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  const runAnalysis = useCallback(async (currentFen: string) => {
    setLoading(true);
    setError(null);
    setSaveSuccessMsg(null);
    try {
      const bestMoveData = await api.predictBestMoves(currentFen);

      const rawCandidates = bestMoveData.candidate_moves || bestMoveData.top_candidates || [];
      const topCandidates: CandidateMove[] = rawCandidates.map((c: any) => ({
        rank: c.rank,
        san: c.san,
        uci: c.uci || c.move,
        evaluationText:
          typeof c.evaluation === 'object' ? c.evaluation.display_text : (c.evaluation || '+0.0'),
        scoreCentipawns:
          typeof c.evaluation === 'object' ? c.evaluation.score_white_cp : (c.evaluation_cp || 0),
        winProbability: c.win_probability,
        qualityTier: c.quality_tier || (c.rank === 1 ? 'excellent' : c.rank === 2 ? 'good' : 'inaccuracy'),
        pv: c.pv_san || c.pv || [],
        isTopRecommendation: Boolean(c.is_best_move || c.rank === 1),
      }));

      try {
        const opponentData = await api.predictOpponentResponses(currentFen);
        if (opponentData.predictions && opponentData.predictions.length > 0) {
          const firstOpp = opponentData.predictions[0];
          if (firstOpp.responses && firstOpp.responses.length > 0) {
            const oppReply = firstOpp.responses[0];
            if (topCandidates.length > 0) {
              topCandidates[0].opponentReplySan = oppReply.move_san;
              topCandidates[0].opponentReplyUci = oppReply.move_uci;
              topCandidates[0].tacticalThreat = oppReply.tactical_threat;
            }
            setTacticalThreat(oppReply.tactical_threat);
          }
        }
      } catch {
        // Fallback gracefully
      }

      setCandidates(topCandidates);
      if (bestMoveData.best_move) {
        setBestMove({ san: bestMoveData.best_move.san, uci: bestMoveData.best_move.uci });
      } else if (topCandidates.length > 0) {
        setBestMove({ san: topCandidates[0].san, uci: topCandidates[0].uci });
      } else {
        setBestMove(null);
      }

      if (topCandidates.length > 0) {
        setSelectedCandidate(topCandidates[0]);
        setScoreCentipawns(topCandidates[0].scoreCentipawns || 0);
        setEvaluationText(topCandidates[0].evaluationText || '+0.0');
      } else {
        setScoreCentipawns(0);
        setEvaluationText('+0.0');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to analyze chess position.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    runAnalysis(game.fen());
  }, [game, runAnalysis]);

  const onDrop = (sourceSquare: Square, targetSquare: Square): boolean => {
    try {
      const newGame = new Chess(game.fen());
      const move = newGame.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q',
      });

      if (!move) return false;

      setGame(newGame);
      setFenInput(newGame.fen());
      return true;
    } catch {
      return false;
    }
  };

  const handleLoadFen = (fenToLoad: string) => {
    try {
      const newGame = new Chess(fenToLoad.trim());
      setGame(newGame);
      setError(null);
    } catch {
      setError('Invalid FEN format. Please provide a standard 6-field chess FEN.');
    }
  };

  const handleReset = () => {
    const newGame = new Chess();
    setGame(newGame);
    setFenInput(newGame.fen());
    setError(null);
    setSaveSuccessMsg(null);
  };

  const handleSaveAnalysis = async () => {
    if (!user) {
      if (onOpenAuth) onOpenAuth();
      else alert('Please sign in to save analysis to Supabase.');
      return;
    }

    if (!bestMove) {
      alert('Please wait for position analysis to complete before saving.');
      return;
    }

    setIsSavingAnalysis(true);
    setError(null);
    try {
      // 1. Create a game reference for this analyzed position
      const gameRecord = await SupabaseChessService.createGame({
        playerColour: game.turn() === 'w' ? 'white' : 'black',
        opponentType: 'Analysis Board',
        startingFen: game.fen(),
        title: `Analysis: ${bestMove.san} (${evaluationText})`,
      });

      // 2. Save analysis record linked to this game
      await SupabaseChessService.saveGameAnalysis({
        gameId: gameRecord.id,
        bestMove: bestMove.san,
        evaluationScore: scoreCentipawns,
        searchDepth: 3,
        analysisSummary: {
          fen: game.fen(),
          evaluation_text: evaluationText,
          candidates_count: candidates.length,
          top_candidates: candidates.slice(0, 3).map((c) => ({
            san: c.san,
            uci: c.uci,
            eval: c.evaluationText,
            tier: c.qualityTier,
          })),
          tactical_threat: tacticalThreat,
        },
      });

      setSaveSuccessMsg(`Analysis saved to cloud! Viewable anytime in "My Games".`);
    } catch (err: any) {
      setError(err.message || 'Failed to save analysis to Supabase.');
    } finally {
      setIsSavingAnalysis(false);
    }
  };

  const customArrows: Arrow[] = useMemo(() => {
    const activeMove = selectedCandidate?.uci || bestMove?.uci;
    if (activeMove && activeMove.length >= 4) {
      const from = activeMove.slice(0, 2);
      const to = activeMove.slice(2, 4);
      return [{ startSquare: from, endSquare: to, color: 'rgba(21, 128, 61, 0.85)' }];
    }
    return [];
  }, [selectedCandidate, bestMove]);

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="page-title">Game Analysis</h1>
          <p className="page-description">
            Explore moves and evaluate any chess position with candidate rankings.
          </p>
        </div>

        {/* FEN Loader Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', maxWidth: '520px', width: '100%' }}>
          <input
            type="text"
            className="text-input"
            value={fenInput}
            onChange={(e) => setFenInput(e.target.value)}
            placeholder="Paste FEN position..."
            style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
          />
          <button onClick={() => handleLoadFen(fenInput)} className="btn btn-secondary">
            Load FEN
          </button>
        </div>
      </div>

      {error && (
        <div className="banner-error" style={{ marginBottom: '16px' }}>
          <span>⚠️ {error}</span>
        </div>
      )}

      {saveSuccessMsg && (
        <div
          style={{
            marginBottom: '16px',
            padding: '8px 14px',
            borderRadius: '4px',
            backgroundColor: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            fontSize: '0.82rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>✓ {saveSuccessMsg}</span>
          <button
            onClick={() => setSaveSuccessMsg(null)}
            style={{ background: 'none', border: 'none', color: '#166534', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      <div className="chess-grid" style={{ gridTemplateColumns: 'minmax(360px, 520px) minmax(320px, 1fr)' }}>
        {/* Left: Board & Eval Bar */}
        <div>
          <div className="board-container" style={{ display: 'flex', gap: '14px', alignItems: 'center', justifyContent: 'center' }}>
            <EvaluationBar
              scoreCentipawns={scoreCentipawns}
              evaluationText={evaluationText}
              isFlipped={orientation === 'black'}
              height={440}
            />

            <div style={{ width: '440px', maxWidth: '100%' }}>
              <Chessboard
                options={{
                  position: game.fen(),
                  boardOrientation: orientation,
                  arrows: customArrows,
                  onPieceDrop: ({ sourceSquare, targetSquare }) =>
                    onDrop(sourceSquare as Square, (targetSquare || '') as Square),
                  darkSquareStyle: { backgroundColor: '#769656' },
                  lightSquareStyle: { backgroundColor: '#eeeed2' },
                  animationDurationInMs: 180,
                }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '14px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={() => runAnalysis(game.fen())}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? 'Analyzing...' : 'Re-analyze'}
            </button>
            <button
              onClick={handleSaveAnalysis}
              disabled={isSavingAnalysis || loading}
              className="btn btn-secondary"
              title="Save current position and engine analysis to Supabase"
            >
              {isSavingAnalysis ? 'Saving...' : '☁️ Save Analysis'}
            </button>
            <button
              onClick={() => setOrientation((o) => (o === 'white' ? 'black' : 'white'))}
              className="btn btn-secondary"
            >
              Flip Board
            </button>
            <button onClick={handleReset} className="btn btn-secondary">
              Reset Position
            </button>
          </div>
        </div>

        {/* Right: Candidates & Diagnostics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <CandidateMovesList
            candidates={candidates}
            selectedMoveUci={selectedCandidate?.uci}
            onSelectCandidate={(cand) => setSelectedCandidate(cand)}
            loading={loading}
          />

          <ExplainableAIPanel
            fen={game.fen()}
            recommendedMoveSan={bestMove?.san}
            tacticalThreat={tacticalThreat}
          />
        </div>
      </div>
    </div>
  );
};

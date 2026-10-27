import React from 'react';
import type { CandidateMove, QualityTier } from '../types';

interface CandidateMovesListProps {
  candidates: CandidateMove[];
  selectedMoveUci?: string;
  onSelectCandidate?: (move: CandidateMove) => void;
  loading?: boolean;
}

const getTierBadge = (tier?: QualityTier) => {
  switch (tier) {
    case 'excellent':
      return <span className="badge badge-excellent">Excellent</span>;
    case 'good':
      return <span className="badge badge-good">Good</span>;
    case 'inaccuracy':
      return <span className="badge badge-inaccuracy">Inaccuracy</span>;
    case 'mistake':
      return <span className="badge badge-mistake">Mistake</span>;
    case 'blunder':
      return <span className="badge badge-blunder">Blunder</span>;
    default:
      return <span className="badge badge-good">Analyzed</span>;
  }
};

export const CandidateMovesList: React.FC<CandidateMovesListProps> = ({
  candidates,
  selectedMoveUci,
  onSelectCandidate,
  loading = false,
}) => {
  if (loading) {
    return (
      <div className="panel" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
          <span className="spin-icon">⏳</span> Analyzing candidate moves...
        </div>
      </div>
    );
  }

  if (!candidates || candidates.length === 0) {
    return (
      <div className="panel" style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        No candidate moves available.
      </div>
    );
  }

  return (
    <div className="panel" style={{ overflow: 'hidden' }}>
      <div className="panel-header">
        <span className="panel-title">Candidate Moves</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Ranked by Minimax Search
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '32px' }}>#</th>
              <th>Move</th>
              <th>Score</th>
              <th>Quality</th>
              <th>Expected Reply</th>
              <th>Continuation</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((cand) => {
              const isSelected = selectedMoveUci === cand.uci;
              const isTop = cand.isTopRecommendation || cand.rank === 1;

              return (
                <tr
                  key={cand.uci}
                  onClick={() => onSelectCandidate?.(cand)}
                  style={{
                    cursor: 'pointer',
                    backgroundColor: isSelected ? '#f1f5f9' : isTop ? '#f8fafc' : undefined,
                  }}
                >
                  <td style={{ fontWeight: 600, color: 'var(--text-dim)' }}>
                    {cand.rank}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.95rem',
                          fontWeight: 700,
                          color: isTop ? '#15803d' : 'var(--text-main)',
                        }}
                      >
                        {cand.san}
                      </span>
                      {isTop && (
                        <span
                          style={{
                            fontSize: '0.65rem',
                            padding: '1px 4px',
                            borderRadius: '3px',
                            backgroundColor: '#dcfce7',
                            color: '#15803d',
                            fontWeight: 700,
                          }}
                        >
                          BEST
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                      {cand.evaluationText}
                    </span>
                  </td>
                  <td>{getTierBadge(cand.qualityTier)}</td>
                  <td>
                    {cand.opponentReplySan ? (
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#2563eb' }}>
                        {cand.opponentReplySan}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>—</span>
                    )}
                  </td>
                  <td style={{ maxWidth: '200px' }}>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.78rem',
                        color: 'var(--text-muted)',
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={cand.pv?.join(' ')}
                    >
                      {cand.pv && cand.pv.length > 0 ? cand.pv.slice(0, 4).join(' ') : '—'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

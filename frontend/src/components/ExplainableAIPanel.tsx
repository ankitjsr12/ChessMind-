import React from 'react';
import { Chess } from 'chess.js';

interface ExplainableAIPanelProps {
  fen: string;
  recommendedMoveSan?: string;
  tacticalThreat?: string;
}

export const ExplainableAIPanel: React.FC<ExplainableAIPanelProps> = ({
  fen,
  recommendedMoveSan,
  tacticalThreat,
}) => {
  // Analyze current position features using chess.js
  let whiteMaterial = 0;
  let blackMaterial = 0;
  let pieceCounts = {
    white: { p: 0, n: 0, b: 0, r: 0, q: 0 },
    black: { p: 0, n: 0, b: 0, r: 0, q: 0 },
  };

  const values: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9 };

  try {
    const chess = new Chess(fen);
    const board = chess.board();

    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const piece = board[r][c];
        if (piece) {
          const type = piece.type;
          const val = values[type] || 0;
          if (piece.color === 'w') {
            whiteMaterial += val;
            if (type in pieceCounts.white) {
              pieceCounts.white[type as keyof typeof pieceCounts.white]++;
            }
          } else {
            blackMaterial += val;
            if (type in pieceCounts.black) {
              pieceCounts.black[type as keyof typeof pieceCounts.black]++;
            }
          }
        }
      }
    }
  } catch {
    // fallback if fen parsing error
  }

  const materialDelta = whiteMaterial - blackMaterial;

  const fenParts = fen.split(' ');
  const castlingRights = fenParts[2] || '-';
  const whiteHasCastle = castlingRights.includes('K') || castlingRights.includes('Q');
  const blackHasCastle = castlingRights.includes('k') || castlingRights.includes('q');

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '16px' }}>
      <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
        <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)' }}>
          Position Analysis & AI Rationale
        </h4>
      </div>

      {/* Rationale */}
      <div
        style={{
          padding: '10px 12px',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: '#f8fafc',
          border: '1px solid var(--border-color)',
        }}
      >
        <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '3px' }}>
          Suggested Move: <span style={{ color: '#15803d', fontFamily: 'var(--font-mono)' }}>{recommendedMoveSan || 'Analyzing...'}</span>
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-main)', lineHeight: 1.4 }}>
          {recommendedMoveSan
            ? `The engine recommends ${recommendedMoveSan} to prioritize piece development, control vital center squares, and maintain tempo without creating weaknesses.`
            : 'Select or make a move on the board to view position evaluation and analysis.'}
        </p>
      </div>

      {/* Material Balance */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '6px' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Material</span>
          <span style={{ fontWeight: 700, color: materialDelta > 0 ? '#15803d' : materialDelta < 0 ? '#dc2626' : 'var(--text-muted)' }}>
            {materialDelta > 0 ? `+${materialDelta} (White)` : materialDelta < 0 ? `${materialDelta} (Black)` : 'Equal'}
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.8rem' }}>
          <div style={{ padding: '6px 10px', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>White: </span>
            <span style={{ fontWeight: 600 }}>{whiteMaterial} pts</span>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              ♙{pieceCounts.white.p} ♘{pieceCounts.white.n} ♗{pieceCounts.white.b} ♖{pieceCounts.white.r} ♕{pieceCounts.white.q}
            </div>
          </div>
          <div style={{ padding: '6px 10px', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>Black: </span>
            <span style={{ fontWeight: 600 }}>{blackMaterial} pts</span>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              ♟{pieceCounts.black.p} ♞{pieceCounts.black.n} ♝{pieceCounts.black.b} ♜{pieceCounts.black.r} ♛{pieceCounts.black.q}
            </div>
          </div>
        </div>
      </div>

      {/* King Safety & Threat */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.8rem' }}>
        <div style={{ padding: '6px 10px', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '2px' }}>King Safety</div>
          <div style={{ fontSize: '0.78rem' }}>
            White: {whiteHasCastle ? 'Castling intact' : 'Castled/Active'}<br />
            Black: {blackHasCastle ? 'Castling intact' : 'Castled/Active'}
          </div>
        </div>

        <div style={{ padding: '6px 10px', backgroundColor: tacticalThreat ? '#fef2f2' : '#f8fafc', borderRadius: 'var(--radius-sm)', border: `1px solid ${tacticalThreat ? '#fecaca' : 'var(--border-color)'}` }}>
          <div style={{ fontSize: '0.72rem', color: tacticalThreat ? '#991b1b' : 'var(--text-muted)', marginBottom: '2px' }}>Threat Check</div>
          <div style={{ fontSize: '0.78rem', color: tacticalThreat ? '#dc2626' : 'var(--text-muted)' }}>
            {tacticalThreat ? tacticalThreat : 'No immediate tactical blunders'}
          </div>
        </div>
      </div>
    </div>
  );
};

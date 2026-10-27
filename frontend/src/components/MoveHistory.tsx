import React, { useEffect, useRef } from 'react';
import type { MoveRecord } from '../types';

interface MoveHistoryProps {
  history: MoveRecord[];
  currentMoveIndex?: number;
  onMoveSelect?: (index: number) => void;
  height?: number | string;
}

export const MoveHistory: React.FC<MoveHistoryProps> = ({
  history,
  currentMoveIndex,
  onMoveSelect,
  height = 360,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Group moves into pairs: [White, Black]
  const movePairs: Array<{ number: number; white?: MoveRecord; black?: MoveRecord; whiteIndex: number; blackIndex: number }> = [];

  for (let i = 0; i < history.length; i += 2) {
    movePairs.push({
      number: Math.floor(i / 2) + 1,
      white: history[i],
      whiteIndex: i,
      black: history[i + 1],
      blackIndex: i + 1,
    });
  }

  // Auto-scroll to current move
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history.length, currentMoveIndex]);

  return (
    <div className="panel" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <span className="panel-title">Move History</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {history.length} {history.length === 1 ? 'ply' : 'plies'}
        </span>
      </div>

      <div
        ref={scrollRef}
        style={{
          height: typeof height === 'number' ? `${height}px` : height,
          overflowY: 'auto',
          padding: '6px 8px',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.85rem',
        }}
      >
        {movePairs.length === 0 ? (
          <div
            style={{
              padding: '24px 12px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '0.82rem',
              fontFamily: 'var(--font-sans)',
            }}
          >
            No moves yet. Make a move on the board to start the game.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {movePairs.map((pair) => {
                const isWhiteActive = currentMoveIndex === pair.whiteIndex;
                const isBlackActive = currentMoveIndex === pair.blackIndex;

                return (
                  <tr key={pair.number} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td
                      style={{
                        width: '32px',
                        padding: '4px 6px',
                        color: 'var(--text-dim)',
                        fontWeight: 600,
                        fontSize: '0.78rem',
                      }}
                    >
                      {pair.number}.
                    </td>
                    <td style={{ width: '45%', padding: '2px 4px' }}>
                      {pair.white && (
                        <button
                          onClick={() => onMoveSelect?.(pair.whiteIndex)}
                          style={{
                            width: '100%',
                            textAlign: 'left',
                            padding: '3px 6px',
                            borderRadius: '3px',
                            border: 'none',
                            backgroundColor: isWhiteActive ? '#dcfce7' : 'transparent',
                            color: isWhiteActive ? '#15803d' : 'var(--text-main)',
                            fontWeight: isWhiteActive ? 700 : 500,
                            cursor: onMoveSelect ? 'pointer' : 'default',
                            fontFamily: 'inherit',
                          }}
                        >
                          {pair.white.san}
                        </button>
                      )}
                    </td>
                    <td style={{ width: '45%', padding: '2px 4px' }}>
                      {pair.black && (
                        <button
                          onClick={() => onMoveSelect?.(pair.blackIndex)}
                          style={{
                            width: '100%',
                            textAlign: 'left',
                            padding: '3px 6px',
                            borderRadius: '3px',
                            border: 'none',
                            backgroundColor: isBlackActive ? '#dcfce7' : 'transparent',
                            color: isBlackActive ? '#15803d' : 'var(--text-main)',
                            fontWeight: isBlackActive ? 700 : 500,
                            cursor: onMoveSelect ? 'pointer' : 'default',
                            fontFamily: 'inherit',
                          }}
                        >
                          {pair.black.san}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

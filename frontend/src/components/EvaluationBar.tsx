import React from 'react';

interface EvaluationBarProps {
  scoreCentipawns?: number;
  evaluationText?: string;
  isFlipped?: boolean;
  height?: number;
}

export const EvaluationBar: React.FC<EvaluationBarProps> = ({
  scoreCentipawns = 0,
  evaluationText,
  isFlipped = false,
  height = 460,
}) => {
  // Convert centipawns or text to a percentage between 0% and 100% for White
  let whitePercentage = 50;

  if (evaluationText && evaluationText.toLowerCase().includes('mate')) {
    if (evaluationText.startsWith('+') || !evaluationText.startsWith('-')) {
      whitePercentage = 100;
    } else {
      whitePercentage = 0;
    }
  } else if (scoreCentipawns !== undefined) {
    // Sigmoid curve: 400 centipawns = ~75%
    const winProb = 1 / (1 + Math.pow(10, -scoreCentipawns / 400));
    whitePercentage = Math.round(winProb * 100);
    whitePercentage = Math.max(5, Math.min(95, whitePercentage));
  }

  // Display text formatted cleanly
  let displayText = '0.0';
  if (evaluationText) {
    displayText = evaluationText;
  } else if (scoreCentipawns !== undefined) {
    const pawns = (scoreCentipawns / 100).toFixed(1);
    displayText = scoreCentipawns > 0 ? `+${pawns}` : `${pawns}`;
  }

  const fillPercentage = isFlipped ? 100 - whitePercentage : whitePercentage;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '4px',
        userSelect: 'none',
      }}
    >
      <div
        style={{
          width: '24px',
          height: `${height}px`,
          backgroundColor: '#334155', // Black side: dark slate
          borderRadius: '4px',
          overflow: 'hidden',
          position: 'relative',
          border: '1px solid #cbd5e1',
          display: 'flex',
          flexDirection: 'column-reverse',
        }}
        title={`Evaluation: ${displayText}`}
      >
        {/* White side */}
        <div
          style={{
            height: `${fillPercentage}%`,
            width: '100%',
            backgroundColor: '#ffffff',
            transition: 'height 0.3s ease',
          }}
        />

        {/* Numeric Label */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            bottom: fillPercentage > 50 ? '8px' : 'auto',
            top: fillPercentage <= 50 ? '8px' : 'auto',
            transform: 'translateX(-50%)',
            fontSize: '0.68rem',
            fontWeight: 700,
            padding: '1px 3px',
            borderRadius: '2px',
            backgroundColor: fillPercentage > 50 ? 'rgba(0, 0, 0, 0.75)' : 'rgba(255, 255, 255, 0.9)',
            color: fillPercentage > 50 ? '#ffffff' : '#0f172a',
            whiteSpace: 'nowrap',
          }}
        >
          {displayText}
        </div>
      </div>
      <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)', fontWeight: 600 }}>
        EVAL
      </span>
    </div>
  );
};

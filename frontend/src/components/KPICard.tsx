import React from 'react';

export interface KPICardProps {
  question: string;
  title: string;
  value: string | number;
  unit?: string;
  plainEnglish: string;
  whyCare?: string;
  methodology?: string;
  accent?: 'blue' | 'amber' | 'emerald' | 'purple';
  badge?: string;
}

export const KPICard: React.FC<KPICardProps> = ({
  question,
  title,
  value,
  unit,
  plainEnglish,
  whyCare,
  methodology,
  accent = 'blue',
  badge,
}) => {
  const accentClass = 
    accent === 'amber' ? 'bias-card' :
    accent === 'blue' ? 'mae-card' : 'p90-card';

  return (
    <div className={`primary-kpi-card ${accentClass}`}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
          <span className="card-question">{question}</span>
          {badge && <span className="assumption-tag">{badge}</span>}
        </div>
        <div className="card-num-row">
          <span className="card-big-num tabular-nums">{value}</span>
          {unit && <span className="card-unit">{unit}</span>}
        </div>
        <div className="card-plain-interpretation">
          {plainEnglish}
        </div>
      </div>

      {(whyCare || methodology) && (
        <details className="card-disclosure">
          <summary>Why this matters & methodology ▾</summary>
          <div className="disclosure-content">
            {whyCare && (
              <p style={{ marginBottom: '6px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Why care: </strong>
                {whyCare}
              </p>
            )}
            {methodology && (
              <div>
                <span className="technical-tag">{title}</span>
                <p style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                  {methodology}
                </p>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
};

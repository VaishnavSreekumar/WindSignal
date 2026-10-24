import React from 'react';

interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  accent?: 'blue' | 'amber' | 'emerald' | 'purple';
  icon?: React.ReactNode;
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  unit,
  subtitle,
  accent = 'blue',
  icon,
}) => {
  return (
    <div className={`kpi-card accent-${accent}`}>
      <div className="kpi-header">
        <span className="kpi-title">{title}</span>
        {icon && <span style={{ color: 'var(--text-dim)' }}>{icon}</span>}
      </div>
      <div className="kpi-value-row">
        <span className="kpi-value">{value}</span>
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {subtitle && <div className="kpi-footer">{subtitle}</div>}
    </div>
  );
};

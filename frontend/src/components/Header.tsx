import React, { useState, useEffect } from 'react';
import { Wind, Activity, Layers, BarChart2, ShieldCheck } from 'lucide-react';
import { HealthResponse } from '../types/api';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  health: HealthResponse | null;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab, health }) => {
  const [utcTime, setUtcTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="terminal-header">
      <div className="header-inner">
        <div className="brand-section">
          <div className="brand-icon">
            <Wind size={18} />
          </div>
          <div>
            <h1 className="brand-title">WindSignal</h1>
            <div className="brand-subtitle">UK Day-Ahead Wind Forecast Intelligence</div>
          </div>
        </div>

        <nav className="nav-tabs" role="tablist" aria-label="Main Navigation">
          <button
            role="tab"
            aria-selected={activeTab === 'cockpit'}
            className={`tab-btn ${activeTab === 'cockpit' ? 'active' : ''}`}
            onClick={() => setActiveTab('cockpit')}
          >
            <Activity size={15} />
            Decision Cockpit
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'vintage'}
            className={`tab-btn ${activeTab === 'vintage' ? 'active' : ''}`}
            onClick={() => setActiveTab('vintage')}
          >
            <Layers size={15} />
            Vintage Explorer
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'accuracy'}
            className={`tab-btn ${activeTab === 'accuracy' ? 'active' : ''}`}
            onClick={() => setActiveTab('accuracy')}
          >
            <BarChart2 size={15} />
            Accuracy Analysis
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'quality'}
            className={`tab-btn ${activeTab === 'quality' ? 'active' : ''}`}
            onClick={() => setActiveTab('quality')}
          >
            <ShieldCheck size={15} />
            Data Quality &amp; Methodology
          </button>
        </nav>

        <div className="header-status">
          <div className="status-indicator" title="Backend Dataset Ready">
            <span className="status-dot"></span>
            {health?.dataset_ready ? `DATASET READY (${health.evaluated_rows}h)` : 'INITIALIZING'}
          </div>
          <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{utcTime}</span>
        </div>
      </div>
    </header>
  );
};

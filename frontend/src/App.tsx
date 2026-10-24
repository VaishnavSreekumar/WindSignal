import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { CockpitView } from './components/CockpitView';
import { VintageExplorerView } from './components/VintageExplorerView';
import { AccuracyAnalysisView } from './components/AccuracyAnalysisView';
import { DataQualityView } from './components/DataQualityView';
import {
  HealthResponse,
  OverviewResponse,
  ForecastVsActualResponse,
  AccuracyMetricsResponse,
  DataQualityResponse,
} from './types/api';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('cockpit');
  
  // Data states
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQualityResponse | null>(null);
  const [timeSeries, setTimeSeries] = useState<ForecastVsActualResponse | null>(null);
  const [accuracy, setAccuracy] = useState<AccuracyMetricsResponse | null>(null);

  // Filters
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // Status
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Initial metadata fetch
  const loadInitialData = async () => {
    try {
      const [h, ov, dq] = await Promise.all([
        api.getHealth(),
        api.getOverview(),
        api.getDataQuality(),
      ]);
      setHealth(h);
      setOverview(ov);
      setDataQuality(dq);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to WindSignal backend API');
    }
  };

  // Time-series and filtered metrics fetch
  const loadFilteredData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ts, acc] = await Promise.all([
        api.getForecastVsActual(dateFrom, dateTo),
        api.getAccuracy(dateFrom, dateTo),
      ]);
      setTimeSeries(ts);
      setAccuracy(acc);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch forecast and accuracy data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    loadFilteredData();
  }, [dateFrom, dateTo]);

  return (
    <div className="app-container">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
      />

      <main className="main-content">
        {activeTab === 'cockpit' && (
          <CockpitView
            overview={overview}
            timeSeries={timeSeries}
            accuracy={accuracy}
            loading={loading}
            error={error}
            dateFrom={dateFrom}
            dateTo={dateTo}
            setDateFrom={setDateFrom}
            setDateTo={setDateTo}
            onRefresh={loadFilteredData}
          />
        )}

        {activeTab === 'vintage' && (
          <VintageExplorerView />
        )}

        {activeTab === 'accuracy' && (
          <AccuracyAnalysisView
            timeSeries={timeSeries}
            accuracy={accuracy}
            loading={loading}
          />
        )}

        {activeTab === 'quality' && (
          <DataQualityView
            dataQuality={dataQuality}
            loading={loading}
          />
        )}
      </main>

      <footer style={{
        borderTop: '1px solid var(--border-subtle)',
        padding: '16px 24px',
        textAlign: 'center',
        fontSize: '11px',
        color: 'var(--text-dim)',
        fontFamily: 'var(--font-mono)'
      }}>
        <span>WindSignal Intelligence Engine v1.0 • Elexon BMRS Stream Provenance (FUELHH & WINDFOR) • Zero Look-Ahead Bias Verified</span>
      </footer>
    </div>
  );
};

export default App;

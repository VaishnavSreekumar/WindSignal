import React, { useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import {
  Calendar,
  AlertTriangle,
  Download,
  Clock,
  RotateCcw,
  TrendingUp,
  ShieldAlert,
} from 'lucide-react';
import {
  OverviewResponse,
  ForecastVsActualResponse,
  AccuracyMetricsResponse,
} from '../types/api';
import { KPICard } from './KPICard';
import { api } from '../services/api';

interface CockpitViewProps {
  overview: OverviewResponse | null;
  timeSeries: ForecastVsActualResponse | null;
  accuracy: AccuracyMetricsResponse | null;
  loading: boolean;
  error: string | null;
  dateFrom: string;
  dateTo: string;
  setDateFrom: (d: string) => void;
  setDateTo: (d: string) => void;
  onRefresh: () => void;
}

export const CockpitView: React.FC<CockpitViewProps> = ({
  overview,
  timeSeries,
  accuracy,
  loading,
  error,
  dateFrom,
  dateTo,
  setDateFrom,
  setDateTo,
  onRefresh,
}) => {
  const [activePreset, setActivePreset] = useState<string>('full');

  const handlePreset = (preset: string) => {
    setActivePreset(preset);
    if (preset === 'full') {
      setDateFrom('');
      setDateTo('');
    } else if (preset === 'h1') {
      setDateFrom('2026-01-02');
      setDateTo('2026-01-16');
    } else if (preset === 'h2') {
      setDateFrom('2026-01-17');
      setDateTo('2026-02-01');
    } else if (preset === 'peak-error') {
      // 3 days around peak error event (Jan 28-30)
      setDateFrom('2026-01-28');
      setDateTo('2026-01-30');
    }
  };

  // Format time series data for Recharts
  const chartData = (timeSeries?.data || []).map((item) => ({
    time: item.delivery_start_time_utc.substring(5, 16).replace('T', ' '),
    rawTimestamp: item.delivery_start_time_utc,
    actual: Math.round(item.actual_generation_mean_mw),
    forecast: Math.round(item.forecast_generation_mw),
    error: Math.round(item.forecast_error_mw),
    leadTime: item.lead_time_hours,
  }));

  const metrics = accuracy || overview?.headline_metrics;

  return (
    <div>
      {/* Context Banner: Decision Window, Delivery Scope, and Assumption Tag */}
      <div className="cockpit-banner">
        <div className="banner-item">
          <span className="banner-label">Decision Dates (D-1)</span>
          <span className="banner-value">
            <Calendar size={14} style={{ color: 'var(--color-forecast)' }} />
            2026-01-01 → 2026-01-31 (31 Days)
          </span>
        </div>

        <div className="banner-item">
          <span className="banner-label">Target Delivery Window (D)</span>
          <span className="banner-value">
            2026-01-02 00:00Z → 2026-02-01 23:00Z (744 Hours)
          </span>
        </div>

        <div className="banner-item">
          <span className="banner-label">Configured Decision Cutoff</span>
          <span className="banner-value">
            <Clock size={14} style={{ color: 'var(--color-cutoff)' }} />
            09:20:00 UTC
            <span className="assumption-tag" title="EPEX SPOT GB 60-min Auction Gate Closure. Internal utility trading mandate is an analytical assumption.">
              Analytical Assumption
            </span>
          </span>
        </div>

        <div className="banner-item">
          <span className="banner-label">Benchmark Run Selected</span>
          <span className="banner-value" style={{ color: 'var(--color-forecast)' }}>
            07:30 UTC NGESO Run
          </span>
        </div>
      </div>

      {/* Date Filter & Control Bar */}
      <div className="panel" style={{ padding: '16px 20px', marginBottom: '20px' }}>
        <div className="panel-header" style={{ margin: 0 }}>
          <div className="filter-bar">
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
              DELIVERY WINDOW:
            </span>
            <div className="filter-btn-group">
              <button
                className={`filter-pill ${activePreset === 'full' ? 'active' : ''}`}
                onClick={() => handlePreset('full')}
              >
                Full Window (744h)
              </button>
              <button
                className={`filter-pill ${activePreset === 'h1' ? 'active' : ''}`}
                onClick={() => handlePreset('h1')}
              >
                Jan 02–16
              </button>
              <button
                className={`filter-pill ${activePreset === 'h2' ? 'active' : ''}`}
                onClick={() => handlePreset('h2')}
              >
                Jan 17–Feb 01
              </button>
              <button
                className={`filter-pill ${activePreset === 'peak-error' ? 'active' : ''}`}
                onClick={() => handlePreset('peak-error')}
              >
                Peak Ramp (Jan 28–30)
              </button>
            </div>

            <div className="date-inputs">
              <input
                type="date"
                className="date-input"
                value={dateFrom}
                min="2026-01-02"
                max="2026-02-01"
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setActivePreset('custom');
                }}
                aria-label="Filter Start Date"
              />
              <span style={{ color: 'var(--text-dim)' }}>→</span>
              <input
                type="date"
                className="date-input"
                value={dateTo}
                min="2026-01-02"
                max="2026-02-01"
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setActivePreset('custom');
                }}
                aria-label="Filter End Date"
              />
            </div>

            {(dateFrom || dateTo) && (
              <button
                className="filter-pill"
                onClick={() => handlePreset('full')}
                title="Reset to full window"
              >
                <RotateCcw size={12} style={{ marginRight: '4px' }} />
                Reset
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={onRefresh}
              className="export-btn"
              title="Refresh time-series data"
            >
              <RotateCcw size={13} />
              Refresh
            </button>
            <a
              href={api.getExportCsvUrl(dateFrom, dateTo)}
              className="export-btn"
              download
              title="Export hourly forecast vs actual CSV"
            >
              <Download size={13} />
              Export CSV
            </a>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Headline KPI Cards */}
      <div className="kpi-grid">
        <KPICard
          title="MEAN ABSOLUTE ERROR"
          value={metrics ? metrics.mae_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle={`Normalized: ${metrics ? metrics.normalized_mae_pct : '—'}% of mean actual`}
          accent="blue"
        />
        <KPICard
          title="ROOT MEAN SQUARED ERROR"
          value={metrics ? metrics.rmse_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle="Penalizes large ramp deviations"
          accent="purple"
        />
        <KPICard
          title="MEAN BIAS ERROR"
          value={metrics ? (metrics.mean_bias_error_mw > 0 ? `+${metrics.mean_bias_error_mw.toLocaleString()}` : metrics.mean_bias_error_mw.toLocaleString()) : '—'}
          unit="MW"
          subtitle={metrics && metrics.mean_bias_error_mw > 0 ? "Systematic Overforecast (+1.75 GW)" : "Underforecast"}
          accent="amber"
          icon={<TrendingUp size={16} style={{ color: 'var(--color-overforecast)' }} />}
        />
        <KPICard
          title="P90 ABSOLUTE ERROR"
          value={metrics ? metrics.p90_abs_error_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle="90% of hours error is below this"
          accent="amber"
        />
        <KPICard
          title="MEAN ACTUAL OUTTURN"
          value={metrics ? metrics.mean_actual_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle="GB Metered Transmission Wind"
          accent="emerald"
        />
        <KPICard
          title="DELIVERY INTERVAL COVERAGE"
          value={accuracy ? `${accuracy.matched_intervals} / ${accuracy.expected_intervals}` : (overview ? `${overview.delivery_window.total_hours}h` : '—')}
          unit={accuracy ? `(${accuracy.coverage_percentage}%)` : '100%'}
          subtitle="0 Missing Intervals"
          accent="emerald"
        />
      </div>

      {/* Primary Forecast vs Actual Time-Series Chart */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">
              Hourly Wind Generation: Day-Ahead Forecast vs. Actual Outturn
            </h2>
            <p className="panel-subtitle">
              Comparison between NGESO WINDFOR (selected at 09:20 UTC cutoff) and FUELHH Outturn. Error convention: Forecast − Actual (positive = overforecast).
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="badge badge-eligible">09:20 Cutoff Applied</span>
            <span className="badge badge-pass">Zero Look-Ahead Bias</span>
          </div>
        </div>

        {loading ? (
          <div className="state-container">
            <div className="state-spinner"></div>
            <p style={{ color: 'var(--text-muted)' }}>Loading time-series analytics from backend...</p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="state-container">
            <ShieldAlert size={32} style={{ color: 'var(--text-dim)' }} />
            <p style={{ color: 'var(--text-muted)' }}>No hourly records match the selected date range.</p>
          </div>
        ) : (
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis
                  dataKey="time"
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  interval={Math.floor(chartData.length / 8)}
                />
                <YAxis
                  yAxisId="left"
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(val) => `${(val / 1000).toFixed(0)}k MW`}
                  domain={[0, 'auto']}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(val) => `${val > 0 ? '+' : ''}${val} MW`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)',
                  }}
                  formatter={(val: any, name: any) => {
                    const num = Number(val);
                    if (name === 'error') {
                      return [`${num > 0 ? '+' : ''}${num.toLocaleString()} MW`, 'Forecast Error (FC - Act)'];
                    }
                    return [`${num.toLocaleString()} MW`, name === 'forecast' ? 'Day-Ahead Forecast' : 'Actual Outturn'];
                  }}
                  labelFormatter={(label) => `Interval: ${label} UTC`}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{ paddingBottom: '10px', fontSize: '12px' }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="forecast"
                  name="Day-Ahead Forecast (MW)"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5, fill: '#38bdf8' }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="actual"
                  name="Actual Outturn (MW)"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5, fill: '#10b981' }}
                />
                <Bar
                  yAxisId="right"
                  dataKey="error"
                  name="Signed Error (MW)"
                  fill="#f59e0b"
                  opacity={0.35}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};

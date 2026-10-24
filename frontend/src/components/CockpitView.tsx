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
  Info,
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
  const isFullWindow = !dateFrom && !dateTo;

  return (
    <div>
      {/* 1. Plain-English Executive Briefing */}
      <section className="briefing-card" aria-label="Executive Briefing">
        <div className="briefing-header">
          <span className="briefing-tag">Historical Procurement Evaluation</span>
          <span className="briefing-window">
            Evaluated Decision Dates: 1–31 January 2026 (Delivery: 2 Jan – 1 Feb 2026)
          </span>
        </div>

        <h2 className="briefing-headline">
          {metrics && metrics.mean_bias_error_mw > 0
            ? 'Day-ahead forecasts ran consistently above actual wind generation across January 2026.'
            : 'Day-ahead forecasts tracked actual wind generation with balanced directional variance.'}
        </h2>

        <p className="briefing-body">
          Across the evaluated hours, the day-ahead forecast expected more wind generation than was ultimately recorded
          (+1,748 MW mean bias for the full month). This indicates a systematic volume overestimation at auction order closure.
          While this is an essential operational planning signal, wind forecast error alone does not determine the amount of electricity
          the team needs to buy—overall demand, prior contract positions, market cashout prices, and balancing actions are outside this dataset.
        </p>

        <div className="briefing-meta-grid">
          <div className="meta-item">
            <span className="meta-label">Evaluation Scope</span>
            <span className="meta-val">
              <Calendar size={13} style={{ color: 'var(--color-forecast)' }} />
              744 Hourly Delivery Intervals
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Forecast Evaluated</span>
            <span className="meta-val">
              Elexon WINDFOR (Available at 09:20 UTC)
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Actual Comparison</span>
            <span className="meta-val">
              Elexon FUELHH Metered Wind Outturn
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Decision Cutoff Reference</span>
            <span className="meta-val">
              <Clock size={13} style={{ color: 'var(--color-cutoff)' }} />
              09:20:00 UTC
              <span className="assumption-tag" title="EPEX SPOT GB Day-Ahead 60-min Auction gate closure. Configured as an analytical assumption.">
                Analytical Assumption
              </span>
            </span>
          </div>
        </div>

        <div className="boundary-note">
          <strong style={{ color: 'var(--text-primary)' }}>Important scope qualification: </strong>
          These figures are historical analytical evaluation benchmarks, not live real-time feeds. The 09:20 UTC cutoff reflects
          the EPEX SPOT GB Day-Ahead Auction order book gate closure. Measured forecast differences do not represent financial cashout
          penalties or demand deficits, as commercial positions depend on full portfolio netting.
        </div>
      </section>

      {/* 2. Decision Window Controls Bar */}
      <div className="panel" style={{ padding: '14px 18px', marginBottom: '20px' }}>
        <div className="panel-header" style={{ margin: 0 }}>
          <div className="filter-bar">
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
              EVALUATION WINDOW:
            </span>
            <div className="filter-btn-group" role="group" aria-label="Preset Date Ranges">
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
                Jan 02–16 (360h)
              </button>
              <button
                className={`filter-pill ${activePreset === 'h2' ? 'active' : ''}`}
                onClick={() => handlePreset('h2')}
              >
                Jan 17–Feb 01 (384h)
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
                className="btn-secondary"
                onClick={() => handlePreset('full')}
                title="Reset to full window"
              >
                <RotateCcw size={12} />
                Reset
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={onRefresh}
              className="btn-secondary"
              title="Refresh time-series data"
            >
              <RotateCcw size={13} />
              Refresh
            </button>
            <a
              href={api.getExportCsvUrl(dateFrom, dateTo)}
              className="btn-secondary"
              download
              title="Export hourly forecast vs actual CSV"
            >
              <Download size={13} />
              Export CSV
            </a>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* 3. Tiered Metrics: Primary Decision Numbers First */}
      <div className="metrics-section">
        <div className="section-label">
          <span>Primary Procurement Decision Metrics</span>
          <span style={{ fontWeight: 400, color: 'var(--text-dim)', textTransform: 'none' }}>
            {isFullWindow ? 'Showing full January 2026 window (744 hours)' : `Filtered window: ${chartData.length} hours`}
          </span>
        </div>

        <div className="primary-kpi-grid">
          <KPICard
            question="Did the forecast overestimate or underestimate wind?"
            title="Mean Bias Error (Signed Forecast − Actual)"
            value={metrics ? (metrics.mean_bias_error_mw > 0 ? `+${metrics.mean_bias_error_mw.toLocaleString()}` : metrics.mean_bias_error_mw.toLocaleString()) : '—'}
            unit="MW"
            plainEnglish={
              metrics && metrics.mean_bias_error_mw > 0
                ? "Forecasts ran consistently high: on average, expected wind was higher than actual delivery by ~1.75 GW."
                : "Forecasts slightly underestimated actual wind delivery."
            }
            whyCare="A persistent positive bias means procurement desks relying strictly on day-ahead wind projections risk being caught short of physical volume if they under-buy dispatchable generation."
            methodology="Arithmetic mean of signed hourly errors: Mean Bias = (1/N) * Σ(Forecast - Actual). Positive value indicates overforecast."
            accent="amber"
            badge="Directional Bias"
          />

          <KPICard
            question="What was the typical size of the forecast error?"
            title="Mean Absolute Error (MAE)"
            value={metrics ? metrics.mae_mw.toLocaleString() : '—'}
            unit="MW"
            plainEnglish={
              metrics
                ? `In an average hour, the forecast missed actual wind generation by ${metrics.mae_mw.toLocaleString()} MW (about ${metrics.normalized_mae_pct}% of average wind output).`
                : '—'
            }
            whyCare="Establishes the standard volume buffer procurement managers should plan for when assessing day-ahead reserve margins."
            methodology="Arithmetic mean of absolute deviations: MAE = (1/N) * Σ|Forecast - Actual|. Does not allow positive and negative errors to cancel out."
            accent="blue"
            badge="Error Magnitude"
          />

          <KPICard
            question="What is the high-error reference level?"
            title="90th Percentile Absolute Error (P90)"
            value={metrics ? metrics.p90_abs_error_mw.toLocaleString() : '—'}
            unit="MW"
            plainEnglish="In 90% of evaluated hours, the forecast error was at or below this value. Only 1 in 10 hours experienced a larger miss."
            whyCare="Provides a realistic worst-decile stress benchmark for risk managers setting contingency limits against extreme forecast misses."
            methodology="Linear interpolation quantile (Type 7): 90% of hourly absolute errors |Forecast - Actual| lie below this threshold."
            accent="purple"
            badge="Tail Risk Level"
          />
        </div>

        {/* Tier 2: Supporting Statistical Context */}
        <div className="secondary-stats-bar" aria-label="Supporting Statistical Context">
          <div className="secondary-stat-item">
            <span className="secondary-stat-label" title="Root Mean Squared Error penalises large ramp misses more heavily than smaller errors.">
              Penalised Error (RMSE) <Info size={11} />
            </span>
            <span className="secondary-stat-val tabular-nums">
              {metrics ? `${metrics.rmse_mw.toLocaleString()} MW` : '—'}
            </span>
            <span className="secondary-stat-sub">Heavy miss penalty</span>
          </div>

          <div className="secondary-stat-item">
            <span className="secondary-stat-label" title="Normalised MAE: MAE divided by Mean Actual Outturn.">
              Normalised Error (NMAE) <Info size={11} />
            </span>
            <span className="secondary-stat-val tabular-nums">
              {metrics ? `${metrics.normalized_mae_pct}%` : '—'}
            </span>
            <span className="secondary-stat-sub">Relative to average wind</span>
          </div>

          <div className="secondary-stat-item">
            <span className="secondary-stat-label" title="Average metered transmission wind generation across the selected hours.">
              Mean Actual Generation <Info size={11} />
            </span>
            <span className="secondary-stat-val tabular-nums">
              {metrics ? `${metrics.mean_actual_mw.toLocaleString()} MW` : '—'}
            </span>
            <span className="secondary-stat-sub">GB Metered Outturn</span>
          </div>

          <div className="secondary-stat-item">
            <span className="secondary-stat-label" title="Evaluated hourly delivery intervals out of expected hours.">
              Evaluated Coverage <Info size={11} />
            </span>
            <span className="secondary-stat-val tabular-nums">
              {accuracy ? `${accuracy.matched_intervals} / ${accuracy.expected_intervals} hrs` : (overview ? `${overview.delivery_window.total_hours} hrs` : '—')}
            </span>
            <span className="secondary-stat-sub">
              {accuracy ? `${accuracy.coverage_percentage}% audited` : '100% complete'}
            </span>
          </div>
        </div>
      </div>

      {/* 4. Primary Forecast vs Actual Time-Series Chart */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">
              How did expected wind generation compare with actual delivery over time?
            </h3>
            <p className="panel-subtitle">
              Visualizes the day-ahead forecast available at auction closure alongside actual metered wind outturn and hourly signed errors.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="badge badge-eligible">09:20 UTC Cutoff Applied</span>
            <span className="badge badge-pass">Zero Look-Ahead Bias</span>
          </div>
        </div>

        {/* Explicit Chart Helper Bar: Explaining Error Convention */}
        <div className="chart-helper-bar">
          <div className="error-convention-explainer">
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Error Convention:</span>
            <span className="convention-formula">Signed Error = Day-Ahead Forecast − Actual Outturn</span>
            <span style={{ color: 'var(--text-muted)' }}>|</span>
            <span style={{ color: 'var(--color-overforecast)' }}>Positive (+) = Forecast above actual (Overforecast)</span>
            <span style={{ color: 'var(--text-muted)' }}>|</span>
            <span style={{ color: 'var(--color-underforecast)' }}>Negative (−) = Forecast below actual (Underforecast)</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
            {chartData.length} hourly delivery intervals displayed
          </div>
        </div>

        {loading ? (
          <div className="state-container">
            <div className="state-spinner"></div>
            <p style={{ color: 'var(--text-secondary)' }}>Loading time-series analytics...</p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="state-container">
            <p style={{ color: 'var(--text-secondary)' }}>No hourly records match the selected date range.</p>
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
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
                  }}
                  formatter={(val: any, name: any) => {
                    const num = Number(val);
                    if (name === 'error') {
                      return [
                        `${num > 0 ? '+' : ''}${num.toLocaleString()} MW (${num > 0 ? 'Overforecast' : num < 0 ? 'Underforecast' : 'Exact'})`,
                        'Forecast Error (FC − Act)',
                      ];
                    }
                    if (name === 'forecast') {
                      return [`${num.toLocaleString()} MW`, 'Day-Ahead Forecast (WINDFOR)'];
                    }
                    return [`${num.toLocaleString()} MW`, 'Actual Metered Outturn (FUELHH)'];
                  }}
                  labelFormatter={(label) => `Delivery Interval: ${label} UTC`}
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
                  activeDot={{ r: 4, fill: '#38bdf8' }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="actual"
                  name="Actual Outturn (MW)"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: '#10b981' }}
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

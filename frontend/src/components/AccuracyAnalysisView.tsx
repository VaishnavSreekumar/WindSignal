import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  ReferenceLine,
} from 'recharts';
import { ForecastVsActualResponse, AccuracyMetricsResponse } from '../types/api';
import { KPICard } from './KPICard';

interface AccuracyAnalysisViewProps {
  timeSeries: ForecastVsActualResponse | null;
  accuracy: AccuracyMetricsResponse | null;
  loading: boolean;
}

export const AccuracyAnalysisView: React.FC<AccuracyAnalysisViewProps> = ({
  timeSeries,
  accuracy,
  loading,
}) => {
  const records = timeSeries?.data || [];
  const sampleSize = records.length;

  // 1. Calculate Daily Aggregations (Daily MAE, Signed Bias, and Outturn)
  const dailyTrends = useMemo(() => {
    if (records.length === 0) return [];

    const grouped: Record<string, { errors: number[]; absErrors: number[]; actuals: number[] }> = {};
    records.forEach((r) => {
      if (!grouped[r.delivery_date]) {
        grouped[r.delivery_date] = { errors: [], absErrors: [], actuals: [] };
      }
      grouped[r.delivery_date].errors.push(r.forecast_error_mw);
      grouped[r.delivery_date].absErrors.push(r.abs_error_mw);
      grouped[r.delivery_date].actuals.push(r.actual_generation_mean_mw);
    });

    return Object.entries(grouped)
      .map(([dDate, vals]) => {
        const count = vals.errors.length;
        const mae = vals.absErrors.reduce((a, b) => a + b, 0) / count;
        const bias = vals.errors.reduce((a, b) => a + b, 0) / count;
        const meanAct = vals.actuals.reduce((a, b) => a + b, 0) / count;
        return {
          date: dDate.substring(5), // MM-DD
          fullDate: dDate,
          mae: Math.round(mae),
          bias: Math.round(bias),
          actualOutturn: Math.round(meanAct),
        };
      })
      .sort((a, b) => a.fullDate.localeCompare(b.fullDate));
  }, [records]);

  // 2. Calculate Forecast Error Distribution Bins (forecast - actual)
  const errorDistribution = useMemo(() => {
    if (records.length === 0) return [];

    const bins = [
      { label: '< -3k MW', min: -Infinity, max: -3000, count: 0, color: '#f43f5e' },
      { label: '-3k to -2k', min: -3000, max: -2000, count: 0, color: '#fb7185' },
      { label: '-2k to -1k', min: -2000, max: -1000, count: 0, color: '#fda4af' },
      { label: '-1k to 0', min: -1000, max: 0, count: 0, color: '#cbd5e1' },
      { label: '0 to +1k', min: 0, max: 1000, count: 0, color: '#fef08a' },
      { label: '+1k to +2k', min: 1000, max: 2000, count: 0, color: '#fde047' },
      { label: '+2k to +3k', min: 2000, max: 3000, count: 0, color: '#facc15' },
      { label: '+3k to +4k', min: 3000, max: 4000, count: 0, color: '#fbbf24' },
      { label: '+4k to +5k', min: 4000, max: 5000, count: 0, color: '#f59e0b' },
      { label: '> +5k MW', min: 5000, max: Infinity, count: 0, color: '#d97706' },
    ];

    records.forEach((r) => {
      const err = r.forecast_error_mw;
      const bin = bins.find((b) => err >= b.min && err < b.max);
      if (bin) {
        bin.count += 1;
      }
    });

    return bins.map((b) => ({
      range: b.label,
      hours: b.count,
      percentage: ((b.count / records.length) * 100).toFixed(1),
      color: b.color,
      isOverforecast: b.min >= 0,
    }));
  }, [records]);

  return (
    <div>
      {/* 1. Practical Executive Takeaway Briefing */}
      <section className="briefing-card" aria-label="Accuracy Practical Takeaways">
        <div className="briefing-header">
          <span className="briefing-tag">Forecasting Performance Analysis</span>
          <span className="briefing-window">
            Evaluated Sample Size: {sampleSize} Hourly Delivery Intervals (N = {sampleSize})
          </span>
        </div>

        <h2 className="briefing-headline">
          Key procurement takeaway: Forecasts ran persistently higher than outturn, with severe positive misses clustered during ramp changes.
        </h2>

        <p className="briefing-body">
          Across the evaluated January 2026 delivery window, the day-ahead forecast missed metered wind by an average of{' '}
          <strong>2,039 MW (18.1% of mean wind)</strong>. Directional bias was overwhelmingly positive (+1,748 MW mean bias),
          meaning the models regularly expected wind that failed to materialize. In 10% of hours (the P90 tail), errors exceeded{' '}
          <strong>4,098 MW</strong>.
        </p>

        <div className="briefing-meta-grid">
          <div className="meta-item">
            <span className="meta-label">Typical Error (MAE)</span>
            <span className="meta-val tabular-nums">
              {accuracy ? `${accuracy.mae_mw.toLocaleString()} MW` : '—'}
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Directional Bias (Mean Bias)</span>
            <span className="meta-val tabular-nums" style={{ color: 'var(--color-overforecast)' }}>
              {accuracy ? `+${accuracy.mean_bias_error_mw.toLocaleString()} MW (Overforecast)` : '—'}
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Peak Overforecast Miss</span>
            <span className="meta-val tabular-nums" style={{ color: 'var(--color-overforecast)' }}>
              {accuracy ? `+${accuracy.max_overforecast_mw.toLocaleString()} MW` : '—'}
            </span>
          </div>

          <div className="meta-item">
            <span className="meta-label">Peak Underforecast Miss</span>
            <span className="meta-val tabular-nums" style={{ color: 'var(--color-underforecast)' }}>
              {accuracy ? `${accuracy.max_underforecast_mw.toLocaleString()} MW` : '—'}
            </span>
          </div>
        </div>

        <div className="boundary-note">
          <strong style={{ color: 'var(--text-primary)' }}>Procurement context: </strong>
          Overforecasting wind introduces short-position volume risk (the system has less physical wind than anticipated),
          requiring procurement desks to dispatch thermal generation or absorb imbalance settlement. However, without actual market price
          or customer demand data, physical MW misses cannot be directly equated to commercial P&amp;L outcomes.
        </div>
      </section>

      {/* 2. Headline Accuracy Metrics */}
      <div className="primary-kpi-grid" style={{ marginBottom: '24px' }}>
        <KPICard
          question="Does the forecast usually overestimate or underestimate wind?"
          title="Directional Bias (Mean Bias Error)"
          value={accuracy ? (accuracy.mean_bias_error_mw > 0 ? `+${accuracy.mean_bias_error_mw.toLocaleString()}` : accuracy.mean_bias_error_mw.toLocaleString()) : '—'}
          unit="MW"
          plainEnglish="Forecasts ran ~1.75 GW higher than actual delivery on average across the month."
          whyCare="Consistent overforecasting means procurement desks relying purely on wind expectations will tend to buy too little backup energy."
          methodology="Arithmetic mean of signed differences: (1/N) * Σ(Forecast − Actual). Positive = Overforecast."
          accent="amber"
          badge="Directional"
        />

        <KPICard
          question="What is the typical magnitude of the hourly forecast miss?"
          title="Typical Error Size (Mean Absolute Error)"
          value={accuracy ? accuracy.mae_mw.toLocaleString() : '—'}
          unit="MW"
          plainEnglish={`The forecast differed from actual outturn by an average of ${accuracy ? accuracy.mae_mw.toLocaleString() : '—'} MW per hour (18.1% of mean wind).`}
          whyCare="Determines the typical buffer required for intraday flexibility and spinning reserves."
          methodology="Average absolute error without sign cancellation: (1/N) * Σ|Forecast − Actual|."
          accent="blue"
          badge="Typical Miss"
        />

        <KPICard
          question="How severe are the worst 10% of forecast misses?"
          title="Tail Risk Level (P90 Absolute Error)"
          value={accuracy ? accuracy.p90_abs_error_mw.toLocaleString() : '—'}
          unit="MW"
          plainEnglish="In 90% of hours, the error was smaller than this. In the remaining 10% of hours, the error was larger."
          whyCare="Helps risk managers size worst-decile volume exposure for trading limits and collateral buffers."
          methodology="90th percentile of absolute hourly error distribution via linear interpolation."
          accent="purple"
          badge="P90 Risk Level"
        />
      </div>

      {loading ? (
        <div className="panel state-container">
          <div className="state-spinner"></div>
          <p style={{ color: 'var(--text-secondary)' }}>Calculating statistical distributions...</p>
        </div>
      ) : (
        <>
          {/* 3. Daily Error Trends Chart */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">
                  Did forecasts consistently overestimate or underestimate wind across the month?
                </h3>
                <p className="panel-subtitle">
                  Daily average error magnitude (blue bars) alongside signed directional bias (amber line).
                  Notice that bias remained positive on almost every day of the month, peaking during the late January storm transitions.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-eligible">Daily MAE (Average Miss)</span>
                <span className="badge badge-selected">Signed Bias (Direction)</span>
              </div>
            </div>

            <div className="chart-helper-bar">
              <div className="error-convention-explainer">
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Daily Evaluation:</span>
                <span>Bars show average miss size; line shows whether the day was overforecast (+) or underforecast (−).</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                {dailyTrends.length} delivery days evaluated
              </div>
            </div>

            <div className="chart-container" style={{ height: '360px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={dailyTrends} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis
                    dataKey="date"
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                    tickFormatter={(val) => `${(val / 1000).toFixed(0)}k MW`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontFamily: 'var(--font-mono)',
                    }}
                    formatter={(val: any, name: any) => {
                      const num = Number(val);
                      if (name === 'bias') {
                        return [
                          `${num > 0 ? '+' : ''}${num.toLocaleString()} MW (${num > 0 ? 'Overforecast' : 'Underforecast'})`,
                          'Daily Signed Bias',
                        ];
                      }
                      if (name === 'mae') {
                        return [`${num.toLocaleString()} MW`, 'Daily Typical Miss (MAE)'];
                      }
                      return [`${num.toLocaleString()} MW`, name];
                    }}
                    labelFormatter={(label) => `Delivery Date: 2026-${label}`}
                  />
                  <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
                  <Bar
                    dataKey="mae"
                    name="Daily MAE (MW)"
                    fill="#38bdf8"
                    opacity={0.7}
                    radius={[2, 2, 0, 0]}
                  />
                  <Line
                    type="monotone"
                    dataKey="bias"
                    name="Signed Bias (MW)"
                    stroke="#f59e0b"
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: '#f59e0b' }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 4. Signed Error Distribution Histogram */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">
                  How large were hourly forecast errors?
                </h3>
                <p className="panel-subtitle">
                  Histogram of signed hourly forecast deviations (Forecast − Actual).
                  The distribution is heavily right-skewed, demonstrating that the vast majority of hours were overforecast (amber/yellow).
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-excluded">Negative Error: Underforecast (Rose)</span>
                <span className="badge badge-selected">Positive Error: Overforecast (Amber)</span>
              </div>
            </div>

            <div className="chart-container" style={{ height: '320px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={errorDistribution} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis
                    dataKey="range"
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                    tickFormatter={(val) => `${val}h`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontFamily: 'var(--font-mono)',
                    }}
                    formatter={(val: any, _name: any, item: any) => {
                      const d = item.payload;
                      const type = d.isOverforecast ? 'Overforecast (FC > Act)' : 'Underforecast (FC < Act)';
                      return [`${val} hours (${d.percentage}% of evaluated hours)`, type];
                    }}
                    labelFormatter={(label) => `Error Bucket: ${label}`}
                  />
                  <Bar dataKey="hours" radius={[3, 3, 0, 0]}>
                    {errorDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

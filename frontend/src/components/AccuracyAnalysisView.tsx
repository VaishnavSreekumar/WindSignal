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
  Legend,
  Cell,
  ReferenceLine,
} from 'recharts';
import {
  BarChart2,
  TrendingUp,
  Info,
} from 'lucide-react';
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

  // 1. Calculate Daily Aggregations (Daily MAE, Bias, and Outturn)
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
      { label: '< -3k', min: -Infinity, max: -3000, count: 0, color: '#ec4899' },
      { label: '-3k to -2k', min: -3000, max: -2000, count: 0, color: '#f43f5e' },
      { label: '-2k to -1k', min: -2000, max: -1000, count: 0, color: '#fb7185' },
      { label: '-1k to 0', min: -1000, max: 0, count: 0, color: '#fda4af' },
      { label: '0 to +1k', min: 0, max: 1000, count: 0, color: '#fde68a' },
      { label: '+1k to +2k', min: 1000, max: 2000, count: 0, color: '#fcd34d' },
      { label: '+2k to +3k', min: 2000, max: 3000, count: 0, color: '#fbbf24' },
      { label: '+3k to +4k', min: 3000, max: 4000, count: 0, color: '#f59e0b' },
      { label: '+4k to +5k', min: 4000, max: 5000, count: 0, color: '#d97706' },
      { label: '> +5k', min: 5000, max: Infinity, count: 0, color: '#b45309' },
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
      {/* Accuracy Analytics Overview */}
      <div className="panel" style={{ padding: '20px', marginBottom: '24px' }}>
        <div className="panel-header" style={{ margin: 0 }}>
          <div>
            <h2 className="panel-title">
              <BarChart2 size={18} style={{ color: 'var(--color-forecast)' }} />
              Accuracy Analysis & Statistical Bias Distribution
            </h2>
            <p className="panel-subtitle">
              Granular statistical evaluation of day-ahead wind forecasting performance across January 2026 delivery intervals.
            </p>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <KPICard
          title="MEAN ABSOLUTE ERROR"
          value={accuracy ? accuracy.mae_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle="Average Magnitude Deviation"
          accent="blue"
        />
        <KPICard
          title="MEAN BIAS ERROR"
          value={accuracy ? (accuracy.mean_bias_error_mw > 0 ? `+${accuracy.mean_bias_error_mw.toLocaleString()}` : accuracy.mean_bias_error_mw.toLocaleString()) : '—'}
          unit="MW"
          subtitle="Systematic Overforecast Tendency"
          accent="amber"
          icon={<TrendingUp size={16} style={{ color: 'var(--color-overforecast)' }} />}
        />
        <KPICard
          title="P90 ABSOLUTE ERROR"
          value={accuracy ? accuracy.p90_abs_error_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle="Tail Volatility Exposure"
          accent="purple"
        />
        <KPICard
          title="MAX OVERFORECAST"
          value={accuracy ? `+${accuracy.max_overforecast_mw.toLocaleString()}` : '—'}
          unit="MW"
          subtitle="Peak Volume Shortfall"
          accent="amber"
        />
        <KPICard
          title="MAX UNDERFORECAST"
          value={accuracy ? accuracy.max_underforecast_mw.toLocaleString() : '—'}
          unit="MW"
          subtitle="Peak Volume Spill/Surplus"
          accent="emerald"
        />
      </div>

      {loading ? (
        <div className="panel state-container">
          <div className="state-spinner"></div>
          <p style={{ color: 'var(--text-muted)' }}>Calculating statistical trends...</p>
        </div>
      ) : (
        <>
          {/* Daily MAE & Bias Trends */}
          <div className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">Daily Forecast Error Trends (MAE & Signed Bias)</h3>
            <p className="panel-subtitle">
              Daily average absolute error (blue bars) alongside signed mean bias (amber line). Positive bias indicates daily overforecasting.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span className="badge badge-eligible">Daily MAE (MW)</span>
            <span className="badge badge-selected">Signed Bias (MW)</span>
          </div>
        </div>

        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={dailyTrends} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                tickFormatter={(val) => `${val} MW`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                }}
                formatter={(val: any, name: any) => [
                  `${Number(val).toLocaleString()} MW`,
                  name === 'mae' ? 'Mean Absolute Error' : name === 'bias' ? 'Signed Mean Bias' : 'Actual Outturn',
                ]}
                labelFormatter={(label) => `Delivery Date: 2026-${label}`}
              />
              <Legend verticalAlign="top" align="right" wrapperStyle={{ paddingBottom: '10px', fontSize: '12px' }} />
              <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
              <Bar dataKey="mae" name="Daily MAE (MW)" fill="#0284c7" radius={[4, 4, 0, 0]} opacity={0.8} />
              <Line
                type="monotone"
                dataKey="bias"
                name="Daily Mean Bias (MW)"
                stroke="#f59e0b"
                strokeWidth={3}
                dot={{ r: 3, fill: '#f59e0b' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Error Distribution Histogram */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">Forecast Error Distribution (MW Bins)</h3>
            <p className="panel-subtitle">
              Distribution of hourly signed errors (Forecast − Actual). Notice the significant positive skew (+1,748 MW mean), showing day-ahead forecasts consistently exceeded realized generation.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span className="badge badge-selected">83.7% Overforecast Hours</span>
            <span className="badge badge-eligible">16.3% Underforecast Hours</span>
          </div>
        </div>

        <div className="chart-container" style={{ height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={errorDistribution} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="range" stroke="#64748b" fontSize={11} tickLine={false} />
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
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                }}
                formatter={(val: any, _name: any, item: any) => [
                  `${val} hours (${item.payload.percentage}% of window)`,
                  item.payload.isOverforecast ? 'Overforecast Range' : 'Underforecast Range',
                ]}
              />
              <Bar dataKey="hours" name="Hourly Occurrences" radius={[4, 4, 0, 0]}>
                {errorDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="kpi-footer" style={{ marginTop: '12px' }}>
          <Info size={14} style={{ color: 'var(--color-forecast)' }} />
          <span>
            Binned data represents exactly {records.length} evaluated hourly delivery intervals from 2026-01-02 00:00Z through 2026-02-01 23:00Z.
          </span>
        </div>
      </div>
      </>
      )}
    </div>
  );
};

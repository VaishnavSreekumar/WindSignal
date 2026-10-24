import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
} from 'lucide-react';
import { ForecastVintagesResponse } from '../types/api';
import { api } from '../services/api';

export const VintageExplorerView: React.FC = () => {
  // Default delivery interval in Jan 2026: 2026-01-02 12:00:00 UTC
  const [selectedInterval, setSelectedInterval] = useState<string>('2026-01-02T12:00:00Z');
  const [vintagesData, setVintagesData] = useState<ForecastVintagesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Representative sample delivery intervals for quick navigation
  const sampleIntervals = [
    { label: 'Jan 02 12:00Z (High Wind)', value: '2026-01-02T12:00:00Z' },
    { label: 'Jan 05 08:00Z (Morning Ramp)', value: '2026-01-05T08:00:00Z' },
    { label: 'Jan 15 18:00Z (Evening Peak)', value: '2026-01-15T18:00:00Z' },
    { label: 'Jan 26 07:00Z (Underforecast)', value: '2026-01-26T07:00:00Z' },
    { label: 'Jan 29 14:00Z (Peak Overforecast)', value: '2026-01-29T14:00:00Z' },
    { label: 'Feb 01 12:00Z (End of Window)', value: '2026-02-01T12:00:00Z' },
  ];

  const fetchVintages = async (interval: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getForecastVintages(interval);
      setVintagesData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch historical forecast vintages');
      setVintagesData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVintages(selectedInterval);
  }, [selectedInterval]);

  // Chart data: chronological evolution of forecast runs for this delivery interval
  const chartData = (vintagesData?.vintages || []).map((v) => ({
    pubTime: v.publish_time_utc.substring(5, 16).replace('T', ' '),
    rawPubTime: v.publish_time_utc,
    generation: v.forecast_generation_mw,
    isEligible: v.is_eligible_prior_to_cutoff,
    isSelected: v.is_selected,
    leadTime: v.lead_time_to_delivery_hours,
  }));

  const selectedVintage = vintagesData?.selected_vintage;

  return (
    <div>
      {/* 1. Plain-English Briefing on Forecast Vintages & Look-Ahead Bias */}
      <section className="briefing-card" aria-label="Vintage Explorer Briefing">
        <div className="briefing-header">
          <span className="briefing-tag">Point-in-Time Forecast Selection</span>
          <span className="briefing-window">
            Target Delivery Interval: {selectedInterval.replace('T', ' ').substring(0, 16)} UTC
          </span>
        </div>

        <h2 className="briefing-headline">
          What forecast version was actually available when the trading decision was made?
        </h2>

        <p className="briefing-body">
          A <strong>forecast vintage</strong> is a saved version of a forecast published at a particular time.
          Throughout each day, the system operator (NGESO) publishes updated wind projections as new weather model runs complete.
          For day-ahead electricity purchasing, order books close at <strong>09:20 UTC on D-1</strong> (configured as an analytical assumption).
          Only forecasts published at or before this cutoff could have guided the trader’s decision.
        </p>

        <div className="boundary-note" style={{ marginTop: '12px' }}>
          <strong style={{ color: 'var(--text-primary)' }}>Why can't we use later forecasts? </strong>
          Even if an afternoon or evening forecast was significantly closer to actual generation, the procurement team had to submit
          binding day-ahead orders by 09:20 UTC. Evaluating past procurement using forecasts published after the decision was made is called{' '}
          <strong>look-ahead bias</strong>—it invalidates performance benchmarks by assuming knowledge no human buyer possessed.
        </div>
      </section>

      {/* 2. Delivery Interval Selector Panel */}
      <div className="panel" style={{ padding: '14px 18px', marginBottom: '20px' }}>
        <div className="panel-header" style={{ margin: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
              SELECT DELIVERY INTERVAL:
            </span>
            <select
              className="date-input"
              value={selectedInterval}
              onChange={(e) => setSelectedInterval(e.target.value)}
              style={{ minWidth: '260px' }}
              aria-label="Select Delivery Interval"
            >
              {sampleIntervals.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="badge badge-eligible">Eligible Pre-Cutoff</span>
            <span className="badge badge-excluded">Excluded Post-Cutoff</span>
            <span className="badge badge-selected">Selected Decision Input</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="state-container">
          <div className="state-spinner"></div>
          <p style={{ color: 'var(--text-secondary)' }}>Retrieving publication runs for {selectedInterval}...</p>
        </div>
      ) : vintagesData ? (
        <>
          {/* 3. Decision Timeline Bar: Publication -> Cutoff -> Delivery */}
          <div className="secondary-stats-bar" style={{ marginBottom: '20px' }}>
            <div className="secondary-stat-item">
              <span className="secondary-stat-label">
                1. Latest Eligible Publication
              </span>
              <span className="secondary-stat-val tabular-nums" style={{ color: 'var(--color-forecast)' }}>
                {selectedVintage ? selectedVintage.publish_time_utc.replace('T', ' ').substring(11, 16) : '—'} UTC (D-1)
              </span>
              <span className="secondary-stat-sub">
                {selectedVintage ? `${selectedVintage.forecast_generation_mw.toLocaleString()} MW expected` : '—'}
              </span>
            </div>

            <div style={{ color: 'var(--text-muted)' }}>
              <ArrowRight size={16} />
            </div>

            <div className="secondary-stat-item">
              <span className="secondary-stat-label">
                2. Configured Decision Cutoff
              </span>
              <span className="secondary-stat-val tabular-nums" style={{ color: 'var(--color-cutoff)' }}>
                {vintagesData.cutoff_time_utc.replace('T', ' ').substring(11, 16)} UTC (D-1)
              </span>
              <span className="secondary-stat-sub">
                EPEX SPOT GB Gate Closure <span className="assumption-tag">Assumption</span>
              </span>
            </div>

            <div style={{ color: 'var(--text-muted)' }}>
              <ArrowRight size={16} />
            </div>

            <div className="secondary-stat-item">
              <span className="secondary-stat-label">
                3. Physical Electricity Delivery
              </span>
              <span className="secondary-stat-val tabular-nums" style={{ color: 'var(--color-actual)' }}>
                {vintagesData.delivery_start_time_utc.replace('T', ' ').substring(0, 16)} UTC (D)
              </span>
              <span className="secondary-stat-sub">
                Lead Time: {selectedVintage ? `${selectedVintage.lead_time_to_delivery_hours}h prior` : '—'}
              </span>
            </div>

            <div className="secondary-stat-item">
              <span className="secondary-stat-label">
                Vintage Availability Breakdown
              </span>
              <span className="secondary-stat-val tabular-nums">
                <span style={{ color: 'var(--color-eligible)' }}>{vintagesData.eligible_vintages_count} pre-cutoff</span>
                <span style={{ color: 'var(--text-muted)' }}> / </span>
                <span style={{ color: 'var(--text-dim)' }}>{vintagesData.excluded_vintages_count} post-cutoff</span>
              </span>
              <span className="secondary-stat-sub">Total {vintagesData.total_vintages_available} published runs</span>
            </div>
          </div>

          {/* 4. Forecast Evolution Chart */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">
                  How did the forecast evolve across sequential publications?
                </h3>
                <p className="panel-subtitle">
                  Trace how NGESO's projected wind generation for this specific hour changed with each updated model run.
                  Only publications prior to the cutoff were legally and operationally usable.
                </p>
              </div>
            </div>

            <div className="chart-container" style={{ height: '320px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis
                    dataKey="pubTime"
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    tickLine={false}
                    tickFormatter={(val) => `${(val / 1000).toFixed(1)}k MW`}
                    domain={['auto', 'auto']}
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
                    formatter={(val: any, _name: any, item: any) => {
                      const v = item.payload;
                      const status = v.isSelected
                        ? '★ SELECTED FOR DECISION (Latest pre-cutoff run)'
                        : v.isEligible
                        ? 'Eligible (Available before 09:20 cutoff)'
                        : 'Excluded (Published after cutoff - Look-Ahead Bias)';
                      return [
                        `${Number(val).toLocaleString()} MW (${status})`,
                        `Lead: ${v.leadTime}h before delivery`,
                      ];
                    }}
                    labelFormatter={(label) => `Publication Run: ${label} UTC`}
                  />
                  <Line
                    type="stepAfter"
                    dataKey="generation"
                    name="Forecast Output (MW)"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={(props: any) => {
                      const { cx, cy, payload } = props;
                      if (payload.isSelected) {
                        return (
                          <circle
                            key={`dot-${payload.pubTime}`}
                            cx={cx}
                            cy={cy}
                            r={6}
                            fill="#38bdf8"
                            stroke="#fff"
                            strokeWidth={2}
                          />
                        );
                      }
                      return (
                        <circle
                          key={`dot-${payload.pubTime}`}
                          cx={cx}
                          cy={cy}
                          r={payload.isEligible ? 4 : 3}
                          fill={payload.isEligible ? '#0284c7' : '#475569'}
                          stroke={payload.isEligible ? '#38bdf8' : '#334155'}
                        />
                      );
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 5. Historical Vintages Table */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">Audit Ledger of Historical Forecast Runs</h3>
                <p className="panel-subtitle">
                  Full audit of all {vintagesData.total_vintages_available} forecast publications received from NGESO for delivery hour {vintagesData.delivery_start_time_utc.replace('T', ' ').substring(0, 16)} UTC.
                </p>
              </div>
            </div>

            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Publication Time (UTC)</th>
                    <th>Target Delivery (UTC)</th>
                    <th>Forecast Generation</th>
                    <th>Lead Time to Delivery</th>
                    <th>Cutoff Margin</th>
                    <th>Eligibility Status</th>
                  </tr>
                </thead>
                <tbody>
                  {vintagesData.vintages.map((v) => {
                    const isSelected = v.is_selected;
                    const isEligible = v.is_eligible_prior_to_cutoff;
                    return (
                      <tr key={v.publish_time_utc} className={isSelected ? 'selected-row' : ''}>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Clock size={13} style={{ color: isSelected ? 'var(--color-forecast)' : 'var(--text-dim)' }} />
                          <span className="tabular-nums">{v.publish_time_utc.replace('T', ' ').substring(0, 19)}</span>
                        </td>
                        <td className="tabular-nums">{vintagesData.delivery_start_time_utc.replace('T', ' ').substring(0, 16)}</td>
                        <td className="tabular-nums" style={{ color: isSelected ? 'var(--color-forecast)' : 'var(--text-primary)', fontWeight: isSelected ? 600 : 400 }}>
                          {v.forecast_generation_mw.toLocaleString()} MW
                        </td>
                        <td className="tabular-nums">{v.lead_time_to_delivery_hours} hours</td>
                        <td className="tabular-nums">
                          {v.latency_to_cutoff_hours !== null ? (
                            <span style={{ color: '#38bdf8' }}>+{v.latency_to_cutoff_hours}h before cutoff</span>
                          ) : (
                            <span style={{ color: 'var(--text-dim)' }}>After cutoff</span>
                          )}
                        </td>
                        <td>
                          {isSelected ? (
                            <span className="badge badge-selected">
                              <CheckCircle2 size={11} /> SELECTED (Zero Look-Ahead)
                            </span>
                          ) : isEligible ? (
                            <span className="badge badge-eligible">Eligible Pre-Cutoff</span>
                          ) : (
                            <span className="badge badge-excluded">
                              <XCircle size={11} /> Excluded (Post-Cutoff)
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

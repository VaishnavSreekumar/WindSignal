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
  Layers,
} from 'lucide-react';
import { ForecastVintagesResponse } from '../types/api';
import { api } from '../services/api';

export const VintageExplorerView: React.FC = () => {
  // Default delivery interval in Jan 2026: 2026-01-02 12:00:00 UTC
  const [selectedInterval, setSelectedInterval] = useState<string>('2026-01-02T12:00:00Z');
  const [vintagesData, setVintagesData] = useState<ForecastVintagesResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // List of representative sample delivery intervals for quick navigation
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

  // Find index or cutoff label for visual reference line
  const selectedVintage = vintagesData?.selected_vintage;

  return (
    <div>
      {/* Top Header / Interval Selector */}
      <div className="panel" style={{ padding: '20px', marginBottom: '24px' }}>
        <div className="panel-header" style={{ margin: 0 }}>
          <div>
            <h2 className="panel-title">
              <Layers size={18} style={{ color: 'var(--color-forecast)' }} />
              Forecast Vintage Explorer — Point-in-Time Reconstruction
            </h2>
            <p className="panel-subtitle">
              Inspect all historical NGESO forecast publications targeting a specific delivery hour. Audits the strict exclusion of post-gate-closure publications to eliminate look-ahead bias.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>
              QUICK INTERVALS:
            </span>
            <select
              className="date-input"
              value={selectedInterval}
              onChange={(e) => setSelectedInterval(e.target.value)}
              style={{ minWidth: '220px' }}
              aria-label="Select Delivery Interval"
            >
              {sampleIntervals.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="state-container">
          <div className="state-spinner"></div>
          <p style={{ color: 'var(--text-muted)' }}>Retrieving publication runs for {selectedInterval}...</p>
        </div>
      ) : vintagesData ? (
        <>
          {/* Summary KPI banner for selected interval */}
          <div className="cockpit-banner" style={{ background: 'var(--bg-card)' }}>
            <div className="banner-item">
              <span className="banner-label">Target Delivery Interval</span>
              <span className="banner-value" style={{ color: 'var(--color-actual)' }}>
                {vintagesData.delivery_start_time_utc.replace('T', ' ').substring(0, 16)} UTC
              </span>
            </div>

            <div className="banner-item">
              <span className="banner-label">Decision Date (D-1)</span>
              <span className="banner-value">
                {vintagesData.decision_date}
              </span>
            </div>

            <div className="banner-item">
              <span className="banner-label">Order Book Cutoff</span>
              <span className="banner-value" style={{ color: 'var(--color-cutoff)' }}>
                {vintagesData.cutoff_time_utc.replace('T', ' ').substring(11, 19)} UTC
                <span className="assumption-tag">EPEX 09:20</span>
              </span>
            </div>

            <div className="banner-item">
              <span className="banner-label">Selected Day-Ahead Forecast</span>
              <span className="banner-value" style={{ color: 'var(--color-forecast)' }}>
                {selectedVintage ? `${selectedVintage.forecast_generation_mw.toLocaleString()} MW` : 'None'}
              </span>
            </div>

            <div className="banner-item">
              <span className="banner-label">Lead Time at Cutoff</span>
              <span className="banner-value">
                {selectedVintage ? `${selectedVintage.lead_time_to_delivery_hours}h prior` : '—'}
              </span>
            </div>

            <div className="banner-item">
              <span className="banner-label">Historical Vintages</span>
              <span className="banner-value">
                <span style={{ color: 'var(--color-eligible)' }}>{vintagesData.eligible_vintages_count} Pre-Cutoff</span>
                <span style={{ color: 'var(--text-dim)' }}> / </span>
                <span style={{ color: 'var(--text-muted)' }}>{vintagesData.excluded_vintages_count} Post-Cutoff</span>
              </span>
            </div>
          </div>

          {/* Forecast Evolution Progression Chart */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">
                  Forecast Evolution Across Historical Publications
                </h3>
                <p className="panel-subtitle">
                  Trace how projected wind output changed with each NGESO update. Markers before the vertical line were available before gate closure.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-eligible">Eligible (Pre-09:20)</span>
                <span className="badge badge-excluded">Excluded (Post-09:20)</span>
                <span className="badge badge-selected">Selected Vintage</span>
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
                      borderRadius: '8px',
                      fontSize: '12px',
                      fontFamily: 'var(--font-mono)',
                    }}
                    formatter={(val: any, _name: any, item: any) => {
                      const v = item.payload;
                      const status = v.isSelected
                        ? '★ SELECTED FOR PROCUREMENT (No Look-Ahead)'
                        : v.isEligible
                        ? 'Eligible (Prior to 09:20 Cutoff)'
                        : 'Excluded (Published After 09:20 Cutoff)';
                      return [
                        `${Number(val).toLocaleString()} MW (${status})`,
                        `Lead: ${v.leadTime}h to delivery`,
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

          {/* Historical Vintages Table */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">Publication Audit Ledger</h3>
                <p className="panel-subtitle">
                  Full list of {vintagesData.total_vintages_available} historical forecast publications received from NGESO WINDFOR stream for this target delivery hour.
                </p>
              </div>
            </div>

            <div className="data-table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Publication Time (UTC)</th>
                    <th>Target Delivery (UTC)</th>
                    <th>Forecast MW</th>
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
                          {v.publish_time_utc.replace('T', ' ').substring(0, 19)}
                        </td>
                        <td>{vintagesData.delivery_start_time_utc.replace('T', ' ').substring(0, 16)}</td>
                        <td style={{ color: isSelected ? 'var(--color-forecast)' : 'var(--text-main)' }}>
                          {v.forecast_generation_mw.toLocaleString()} MW
                        </td>
                        <td>{v.lead_time_to_delivery_hours} hours</td>
                        <td>
                          {v.latency_to_cutoff_hours !== null ? (
                            <span style={{ color: '#38bdf8' }}>+{v.latency_to_cutoff_hours}h pre-cutoff</span>
                          ) : (
                            <span style={{ color: 'var(--text-dim)' }}>Post-cutoff</span>
                          )}
                        </td>
                        <td>
                          {isSelected ? (
                            <span className="badge badge-selected">
                              <CheckCircle2 size={11} /> SELECTED VINTAGE
                            </span>
                          ) : isEligible ? (
                            <span className="badge badge-eligible">Eligible Pre-Cutoff</span>
                          ) : (
                            <span className="badge badge-excluded">
                              <XCircle size={11} /> Excluded (Look-Ahead Bias)
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

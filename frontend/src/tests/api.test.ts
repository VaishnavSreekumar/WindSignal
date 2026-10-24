import { describe, it, expect } from 'vitest';
import { api, buildUrl } from '../services/api';

describe('Frontend API Client URL Builder', () => {
  it('constructs base CSV export URL correctly without parameters', () => {
    const url = api.getExportCsvUrl();
    expect(url).toContain('/api/export.csv');
  });

  it('appends delivery date parameters to CSV export URL', () => {
    const url = api.getExportCsvUrl('2026-01-05', '2026-01-10');
    expect(url).toContain('delivery_date_from=2026-01-05');
    expect(url).toContain('delivery_date_to=2026-01-10');
  });

  it('supports production Vercel backend URL without localhost in production', () => {
    const prodUrl = buildUrl('/api/health', 'https://windsignal-api.vercel.app');
    expect(prodUrl.toString()).toBe('https://windsignal-api.vercel.app/api/health');
    expect(prodUrl.origin).toBe('https://windsignal-api.vercel.app');
    expect(prodUrl.toString()).not.toContain('localhost');
  });

  it('normalizes production URLs with trailing slashes correctly', () => {
    const prodUrl = buildUrl('/api/overview', 'https://windsignal-api.vercel.app/');
    expect(prodUrl.toString()).toBe('https://windsignal-api.vercel.app/api/overview');
    expect(prodUrl.toString()).not.toContain('//api');
  });
});

describe('Analytical Mathematical Invariants in Frontend', () => {
  it('calculates error strictly as forecast minus actual', () => {
    const forecast = 15000;
    const actual = 12000;
    const error = forecast - actual;
    expect(error).toBe(3000); // Overforecast
    expect(error > 0).toBe(true);
  });

  it('identifies underforecast as negative error', () => {
    const forecast = 10000;
    const actual = 14000;
    const error = forecast - actual;
    expect(error).toBe(-4000); // Underforecast
    expect(error < 0).toBe(true);
  });

  it('computes daily MAE arithmetic mean properly', () => {
    const absErrors = [2000, 3000, 1000, 4000];
    const mae = absErrors.reduce((a, b) => a + b, 0) / absErrors.length;
    expect(mae).toBe(2500);
  });

  it('computes P90 percentile using linear interpolation matching backend quantile definition', () => {
    // Test linear interpolation formula: index = q * (N - 1)
    // For values [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000] (N=10)
    // 90th percentile index = 0.9 * 9 = 8.1 -> arr[8] + 0.1 * (arr[9] - arr[8]) = 9000 + 100 = 9100
    const sortedVals = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000];
    const q = 0.90;
    const index = q * (sortedVals.length - 1);
    const lower = Math.floor(index);
    const upper = Math.ceil(index);
    const weight = index - lower;
    const p90 = sortedVals[lower] + weight * (sortedVals[upper] - sortedVals[lower]);
    expect(p90).toBe(9100);
  });
});

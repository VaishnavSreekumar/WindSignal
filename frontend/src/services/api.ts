/**
 * WindSignal API Client
 * Connects directly to the FastAPI backend without mock fallbacks.
 */

import {
  HealthResponse,
  OverviewResponse,
  ForecastVsActualResponse,
  AccuracyMetricsResponse,
  ForecastVintagesResponse,
  DataQualityResponse,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function buildUrl(endpoint: string): URL {
  const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  if (API_BASE_URL) {
    const cleanBase = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL;
    return new URL(`${cleanBase}${cleanEndpoint}`, base);
  }
  return new URL(cleanEndpoint, base);
}

async function request<T>(endpoint: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = buildUrl(endpoint);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.append(key, value);
      }
    });
  }

  const response = await fetch(url.toString(), {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(errorDetail, response.status);
  }

  return response.json();
}

export const api = {
  getHealth: (): Promise<HealthResponse> => {
    return request<HealthResponse>('/api/health');
  },

  getOverview: (): Promise<OverviewResponse> => {
    return request<OverviewResponse>('/api/overview');
  },

  getForecastVsActual: (dateFrom?: string, dateTo?: string): Promise<ForecastVsActualResponse> => {
    return request<ForecastVsActualResponse>('/api/forecast-vs-actual', {
      delivery_date_from: dateFrom,
      delivery_date_to: dateTo,
    });
  },

  getAccuracy: (dateFrom?: string, dateTo?: string): Promise<AccuracyMetricsResponse> => {
    return request<AccuracyMetricsResponse>('/api/accuracy', {
      delivery_date_from: dateFrom,
      delivery_date_to: dateTo,
    });
  },

  getForecastVintages: (deliveryStartTime: string): Promise<ForecastVintagesResponse> => {
    return request<ForecastVintagesResponse>('/api/forecast-vintages', {
      delivery_start_time: deliveryStartTime,
    });
  },

  getDataQuality: (): Promise<DataQualityResponse> => {
    return request<DataQualityResponse>('/api/data-quality');
  },

  getExportCsvUrl: (dateFrom?: string, dateTo?: string): string => {
    const url = buildUrl('/api/export.csv');
    if (dateFrom) url.searchParams.append('delivery_date_from', dateFrom);
    if (dateTo) url.searchParams.append('delivery_date_to', dateTo);
    return url.toString();
  },
};

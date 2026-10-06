/**
 * Centralised environment access. Components must never read
 * import.meta.env directly — everything goes through here.
 */

export type DataMode = 'api' | 'mock';

export interface AppEnv {
  dataMode: DataMode;
  apiBaseUrl: string;
}

export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8787/api/v1';

function readEnvValue(key: string): string | undefined {
  const env = import.meta.env as Record<string, string | undefined>;
  const value = env[key];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

export function industryForecastBaseUrl(): string {
  return readEnvValue('VITE_INDUSTRY_FORECAST_API_BASE_URL') ?? 'http://127.0.0.1:3313/api/industry-forecast';
}

export function getAppEnv(): AppEnv {
  const rawMode = readEnvValue('VITE_DATA_MODE');
  // Normal/default mode is the real API. Mock is opt-in only (never a silent fallback).
  const dataMode: DataMode = rawMode === 'mock' ? 'mock' : 'api';
  return {
    dataMode,
    apiBaseUrl: readEnvValue('VITE_RESEARCH_API_BASE_URL') ?? DEFAULT_API_BASE_URL,
  };
}

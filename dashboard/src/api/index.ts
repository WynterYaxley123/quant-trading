import type { ResearchDataPort } from './contracts';
import { createRealApiAdapter } from './adapters/real-api';
import { createMockApiAdapter } from './adapters/mock-api';
import { getAppEnv, type AppEnv } from '@/lib/env';

/**
 * Adapter selection. The default is always the real API; mock mode requires
 * an explicit `VITE_DATA_MODE=mock`. If the real API is offline the UI shows
 * "API disconnected" — it never silently falls back to mock data.
 */
export function createResearchApi(env: AppEnv = getAppEnv()): ResearchDataPort {
  if (env.dataMode === 'mock') {
    return createMockApiAdapter();
  }
  return createRealApiAdapter({ baseUrl: env.apiBaseUrl });
}

let singleton: ResearchDataPort | null = null;

export function getResearchApi(): ResearchDataPort {
  if (!singleton) singleton = createResearchApi();
  return singleton;
}

/** Test-only: swap the port implementation. */
export function setResearchApiForTesting(port: ResearchDataPort | null): void {
  singleton = port;
}

export * from './contracts';
export * from './errors';

import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { getResearchApi } from '@/api';
import type { Capabilities, Health, ResearchStatus, RunSummary } from '@/api/contracts';
import type { ResearchApiError } from '@/api/errors';
import { useResource } from '@/hooks/useResource';
import { getAppEnv, type DataMode } from '@/lib/env';

/**
 * Shell-level data shared across pages (capabilities, research status, run
 * list, data mode). Page-specific data is fetched by each page itself.
 */

export interface AppData {
  capabilities: Capabilities | null;
  status: ResearchStatus | null;
  runs: RunSummary[];
  dataMode: DataMode;
  apiBaseUrl: string;
  loading: boolean;
  error: ResearchApiError | null;
  health: Health | null;
  healthLoading: boolean;
  healthError: ResearchApiError | null;
  artifactState: 'AVAILABLE' | 'NOT_CONFIGURED' | 'DEGRADED' | null;
  retry: () => void;
}

const AppDataContext = createContext<AppData | null>(null);

export function AppDataProvider({ children, enabled=true, observeHealth=true }: { children: ReactNode; enabled?:boolean; observeHealth?:boolean }) {
  const env = useMemo(() => getAppEnv(), []);
  const api = useMemo(() => getResearchApi(), []);
  // Process health never opens an artifact, including on ETF observation pages.
  const health = useResource((signal) => observeHealth ? api.getHealth(signal) : Promise.resolve(null), [api,observeHealth]);

  const shell = useResource(async (signal) => {
    // ETF rendering never opens a Research artifact or depends on its availability.
    if(!enabled) return {capabilities:null,status:null,runs:[]};
    const status = await api.getResearchStatus(signal);
    const [capabilities, runs] = await Promise.all([
      api.getCapabilities(signal),
      status.artifactState === 'DEGRADED' ? Promise.resolve([]) : api.getRuns(signal),
    ]);
    return { capabilities, status, runs };
  }, [api,enabled]);

  const value: AppData = {
    capabilities: shell.data?.capabilities ?? null,
    status: shell.data?.status ?? null,
    runs: shell.data?.runs ?? [],
    dataMode: env.dataMode,
    apiBaseUrl: env.apiBaseUrl,
    loading: shell.loading || health.loading,
    error: health.error ?? shell.error,
    health: health.data,
    healthLoading: health.loading,
    healthError: health.error,
    artifactState: enabled && shell.data ? shell.data.status?.artifactState ?? (shell.data.runs.length ? 'AVAILABLE' : 'NOT_CONFIGURED') : null,
    retry: () => { health.retry(); shell.retry(); },
  };

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData(): AppData {
  const context = useContext(AppDataContext);
  if (!context) {
    throw new Error('useAppData must be used inside <AppDataProvider>');
  }
  return context;
}

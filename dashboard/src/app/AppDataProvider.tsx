import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { getResearchApi } from '@/api';
import type { Capabilities, ResearchStatus, RunSummary } from '@/api/contracts';
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
  retry: () => void;
}

const AppDataContext = createContext<AppData | null>(null);

export function AppDataProvider({ children, enabled=true }: { children: ReactNode; enabled?:boolean }) {
  const env = useMemo(() => getAppEnv(), []);
  const api = useMemo(() => getResearchApi(), []);

  const shell = useResource(async (signal) => {
    // ETF observation never opens a Research artifact or requires Research HTTP.
    if(!enabled) return {capabilities:null,status:null,runs:[]};
    const [capabilities, status, runs] = await Promise.all([
      api.getCapabilities(signal),
      api.getResearchStatus(signal),
      api.getRuns(signal),
    ]);
    return { capabilities, status, runs };
  }, [api,enabled]);

  const value: AppData = {
    capabilities: shell.data?.capabilities ?? null,
    status: shell.data?.status ?? null,
    runs: shell.data?.runs ?? [],
    dataMode: env.dataMode,
    apiBaseUrl: env.apiBaseUrl,
    loading: shell.loading,
    error: shell.error,
    retry: shell.retry,
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

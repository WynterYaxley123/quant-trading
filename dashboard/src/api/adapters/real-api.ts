import {
  candidateListSchema,
  candidateMetricsSchema,
  dailyMetricListSchema,
  diagnosticsSchema,
  healthSchema,
  capabilitiesSchema,
  integritySchema,
  predictionPageSchema,
  researchStatusSchema,
  runDetailSchema,
  runListSchema,
  type CandidateMetrics,
  type CandidateSummary,
  type Capabilities,
  type DailyMetric,
  type DailyMetricsQuery,
  type Diagnostics,
  type Health,
  type Integrity,
  type PredictionsQuery,
  type PredictionPage,
  type ResearchDataPort,
  type ResearchStatus,
  type RunDetail,
  type RunSummary,
} from '../contracts';
import { ResearchApiClient, type QueryValue } from '../client';

/**
 * REAL API adapter — talks to the READ-ONLY Research Data API v1 over HTTP.
 * The integrated dashboard defaults to this adapter. Mock data requires
 * explicit `VITE_DATA_MODE=mock`; network failure never changes adapters.
 */
export function createRealApiAdapter(options: {
  baseUrl: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}): ResearchDataPort {
  const client = new ResearchApiClient(options);

  return {
    async getHealth(signal?: AbortSignal): Promise<Health> {
      return client.get('/health', healthSchema, undefined, signal);
    },

    async getCapabilities(signal?: AbortSignal): Promise<Capabilities> {
      return client.get('/capabilities', capabilitiesSchema, undefined, signal);
    },

    async getResearchStatus(signal?: AbortSignal): Promise<ResearchStatus> {
      return client.get('/research/status', researchStatusSchema, undefined, signal);
    },

    async getRuns(signal?: AbortSignal): Promise<RunSummary[]> {
      const data = await client.get('/runs', runListSchema, undefined, signal);
      return data.items;
    },

    async getRun(runId: string, signal?: AbortSignal): Promise<RunDetail> {
      return client.get(`/runs/${encodeURIComponent(runId)}`, runDetailSchema, undefined, signal);
    },

    async getCandidates(runId: string, signal?: AbortSignal): Promise<CandidateSummary[]> {
      const data = await client.get(
        `/runs/${encodeURIComponent(runId)}/candidates`,
        candidateListSchema,
        undefined,
        signal,
      );
      return data.items;
    },

    async getMetrics(
      runId: string,
      candidateId: string,
      signal?: AbortSignal,
    ): Promise<CandidateMetrics> {
      return client.get(
        `/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/metrics`,
        candidateMetricsSchema,
        undefined,
        signal,
      );
    },

    async getDailyMetrics(
      runId: string,
      candidateId: string,
      query?: DailyMetricsQuery,
      signal?: AbortSignal,
    ): Promise<DailyMetric[]> {
      const data = await client.get(
        `/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/daily-metrics`,
        dailyMetricListSchema,
        { horizon: query?.horizon } as QueryValue,
        signal,
      );
      return data.items;
    },

    async getPredictions(
      runId: string,
      candidateId: string,
      query: PredictionsQuery,
      signal?: AbortSignal,
    ): Promise<PredictionPage> {
      return client.get(
        `/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/predictions`,
        predictionPageSchema,
        {
          date: query.date,
          top5: query.top5,
          limit: query.limit,
          offset: query.offset,
        },
        signal,
      );
    },

    async getDiagnostics(
      runId: string,
      candidateId: string,
      signal?: AbortSignal,
    ): Promise<Diagnostics> {
      return client.get(
        `/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/diagnostics`,
        diagnosticsSchema,
        undefined,
        signal,
      );
    },

    async getIntegrity(runId: string, signal?: AbortSignal): Promise<Integrity> {
      return client.get(`/runs/${encodeURIComponent(runId)}/integrity`, integritySchema, undefined, signal);
    },
  };
}

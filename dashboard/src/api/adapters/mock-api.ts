import type {
  CandidateMetrics,
  CandidateSummary,
  Capabilities,
  DailyMetric,
  DailyMetricsQuery,
  Diagnostics,
  Health,
  Integrity,
  PredictionsQuery,
  PredictionPage,
  ResearchDataPort,
  ResearchStatus,
  RunDetail,
  RunSummary,
} from '../contracts';
import { ResearchApiError } from '../errors';
import {
  mockCandidateMetrics,
  mockCandidates,
  mockCapabilities,
  mockDiagnostics,
  mockDailyMetrics,
  mockHealth,
  mockIntegrity,
  mockPredictionDates,
  mockPredictionRows,
  mockResearchStatus,
  mockRunDetail,
  mockRunSummaries,
  MOCK_RUN_ID,
} from '@/mocks/fixtures';

/**
 * MOCK adapter — returns synthetic fixtures. Selected only via an explicit
 * `VITE_DATA_MODE=mock`; there is never a silent fallback from the real API.
 */
export function createMockApiAdapter(): ResearchDataPort & {
  /** Dates available to the Sector Explorer in mock mode. */
  availableDates(): string[];
} {
  const notFound = (what: string) =>
    new ResearchApiError('RUN_NOT_FOUND', `Mock fixture not found: ${what}`);

  return {
    availableDates: () => [...mockPredictionDates],

    async getHealth(): Promise<Health> {
      return mockHealth;
    },

    async getCapabilities(): Promise<Capabilities> {
      return mockCapabilities;
    },

    async getResearchStatus(): Promise<ResearchStatus> {
      return mockResearchStatus;
    },

    async getRuns(): Promise<RunSummary[]> {
      return mockRunSummaries;
    },

    async getRun(runId: string): Promise<RunDetail> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      return mockRunDetail;
    },

    async getCandidates(runId: string): Promise<CandidateSummary[]> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      return mockCandidates;
    },

    async getMetrics(runId: string, candidateId: string): Promise<CandidateMetrics> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      const metrics = mockCandidateMetrics[candidateId];
      if (!metrics) throw new ResearchApiError('CANDIDATE_NOT_FOUND', `Unknown candidate ${candidateId}`);
      return metrics;
    },

    async getDailyMetrics(
      runId: string,
      candidateId: string,
      query?: DailyMetricsQuery,
    ): Promise<DailyMetric[]> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      if (!mockCandidateMetrics[candidateId]) {
        throw new ResearchApiError('CANDIDATE_NOT_FOUND', `Unknown candidate ${candidateId}`);
      }
      return mockDailyMetrics(candidateId, query?.horizon);
    },

    async getPredictions(
      runId: string,
      candidateId: string,
      query: PredictionsQuery,
    ): Promise<PredictionPage> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      if (!mockCandidateMetrics[candidateId]) {
        throw new ResearchApiError('CANDIDATE_NOT_FOUND', `Unknown candidate ${candidateId}`);
      }
      if (!mockPredictionDates.includes(query.date)) {
        throw new ResearchApiError('BAD_QUERY', `No mock predictions for date ${query.date}`);
      }
      let rows = mockPredictionRows(query.date);
      if (query.top5) rows = rows.filter((row) => row.top5);
      const offset = query.offset ?? 0;
      const limit = query.limit ?? rows.length;
      return {
        items: rows.slice(offset, offset + limit),
        total: rows.length,
        limit,
        offset,
      };
    },

    async getDiagnostics(runId: string): Promise<Diagnostics> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      return mockDiagnostics();
    },

    async getIntegrity(runId: string): Promise<Integrity> {
      if (runId !== MOCK_RUN_ID) throw notFound(runId);
      return mockIntegrity;
    },
  };
}

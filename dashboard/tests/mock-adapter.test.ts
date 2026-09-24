import { describe, expect, it } from 'vitest';
import { createMockApiAdapter } from '@/api/adapters/mock-api';
import {
  candidateMetricsSchema,
  candidateSummarySchema,
  dailyMetricSchema,
  diagnosticsSchema,
  integritySchema,
  predictionSchema,
  researchStatusSchema,
  runDetailSchema,
} from '@/api/contracts';
import { MOCK_RUN_ID } from '@/mocks/fixtures';

/**
 * The mock fixtures are validated against the same zod schemas the real API
 * responses are — a synthetic-data guard and a contract regression test.
 */
describe('mock adapter', () => {
  const api = createMockApiAdapter();

  it('returns contract-shaped synthetic data', async () => {
    expect(researchStatusSchema.parse(await api.getResearchStatus())).toBeDefined();
    expect(runDetailSchema.parse(await api.getRun(MOCK_RUN_ID))).toBeDefined();

    const candidates = await api.getCandidates(MOCK_RUN_ID);
    expect(candidates).toHaveLength(4);
    for (const candidate of candidates) {
      expect(candidateSummarySchema.parse(candidate)).toBeDefined();
    }

    for (const candidateId of ['D0', 'D1', 'D2', 'D3']) {
      expect(candidateMetricsSchema.parse(await api.getMetrics(MOCK_RUN_ID, candidateId))).toBeDefined();
    }

    for (const row of await api.getDailyMetrics(MOCK_RUN_ID, 'D0', { horizon: 10 })) {
      expect(dailyMetricSchema.parse(row)).toBeDefined();
    }

    const page = await api.getPredictions(MOCK_RUN_ID, 'D0', { date: '2025-02-10' });
    expect(page.total).toBe(10);
    for (const row of page.items) {
      expect(predictionSchema.parse(row)).toBeDefined();
    }

    expect(diagnosticsSchema.parse(await api.getDiagnostics(MOCK_RUN_ID, 'D0'))).toBeDefined();
    expect(integritySchema.parse(await api.getIntegrity(MOCK_RUN_ID))).toBeDefined();
  });

  it('uses mixed promotion statuses and null gaps (synthetic)', async () => {
    const candidates = await api.getCandidates(MOCK_RUN_ID);
    const statuses = candidates.map((candidate) => candidate.promotionStatus);
    expect(statuses).toContain('DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW');
    expect(statuses).toContain('NOT_PROMOTED');
    expect(statuses).toContain(null);
    expect(candidates.some((candidate) => candidate.weightedRankIc === null)).toBe(true);
  });

  it('filters predictions by top5 and paginates', async () => {
    const top5 = await api.getPredictions(MOCK_RUN_ID, 'D0', { date: '2025-02-10', top5: true });
    expect(top5.items.every((row) => row.top5)).toBe(true);
    expect(top5.items).toHaveLength(5);

    const paged = await api.getPredictions(MOCK_RUN_ID, 'D0', {
      date: '2025-02-10',
      limit: 3,
      offset: 2,
    });
    expect(paged.items).toHaveLength(3);
    expect(paged.offset).toBe(2);
    expect(paged.total).toBe(10);
  });

  it('raises BAD_QUERY for unknown dates and RUN_NOT_FOUND for unknown runs', async () => {
    await expect(
      api.getPredictions(MOCK_RUN_ID, 'D0', { date: '1999-01-01' }),
    ).rejects.toMatchObject({ code: 'BAD_QUERY' });
    await expect(api.getRun('unknown')).rejects.toMatchObject({ code: 'RUN_NOT_FOUND' });
  });
});

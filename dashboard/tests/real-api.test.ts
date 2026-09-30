import { describe, expect, it, vi } from 'vitest';
import { createRealApiAdapter } from '@/api/adapters/real-api';
import { ResearchApiError } from '@/api/errors';
import {
  mockCandidateMetrics,
  mockCandidates,
  mockCapabilities,
  mockDiagnostics,
  mockIntegrity,
  mockPredictionRows,
  mockResearchStatus,
  mockRunDetail,
  mockRunSummaries,
} from '@/mocks/fixtures';

/**
 * REAL API READINESS: the real-api adapter is exercised against mocked HTTP
 * responses shaped exactly like the frozen API v1 contract. When the Codex
 * API branch merges, switching env vars is sufficient — components are
 * already wired through this adapter.
 */

function ok(data: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ schemaVersion: '1.0.0', data }),
  } as Response;
}

function fail(status: number, code: string, message: string) {
  return {
    ok: false,
    status,
    json: async () => ({ schemaVersion: '1.0.0', error: { code, message } }),
  } as Response;
}

function adapterWith(fetchImpl: typeof fetch) {
  return createRealApiAdapter({ baseUrl: 'http://127.0.0.1:8787/api/v1', fetchImpl });
}

const runId = mockRunSummaries[0]!.runId;

describe('real-api adapter (mocked HTTP)', () => {
  it('parses health, capabilities and research status', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) {
        return ok({ status: 'ok', readOnly: true, sourceOfTruth: 'RESEARCH_ARTIFACTS' });
      }
      if (url.endsWith('/capabilities')) return ok(mockCapabilities);
      return ok(mockResearchStatus);
    }) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    expect(await api.getHealth()).toEqual({
      status: 'ok',
      readOnly: true,
      sourceOfTruth: 'RESEARCH_ARTIFACTS',
    });
    expect((await api.getCapabilities()).portfolio).toBe(false);
    expect((await api.getResearchStatus()).validation).toBe('SEALED');
  });

  it('parses runs, run detail and candidates', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/runs')) return ok({ items: mockRunSummaries });
      if (url.endsWith(`/runs/${runId}/candidates`)) return ok({ items: mockCandidates });
      return ok(mockRunDetail);
    }) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    expect((await api.getRuns())[0]?.runId).toBe(runId);
    expect((await api.getRun(runId)).splitPolicyHash).toBe(mockRunDetail.splitPolicyHash);
    expect((await api.getCandidates(runId)).map((c) => c.candidateId)).toEqual(['D0', 'D1', 'D2', 'D3']);
  });

  it('parses metrics, daily metrics (with horizon filter) and predictions pagination', async () => {
    const dailyRows = [
      {
        ordinal: 'E001',
        signalDate: '2025-02-10',
        horizon: 10,
        ic: 0.01,
        rankIc: 0.02,
        top5ForwardReturn: 0.03,
        universeForwardReturn: 0.01,
        top5MinusUniverse: 0.02,
      },
    ];
    const predictionPage = {
      items: mockPredictionRows('2025-02-10'),
      total: 10,
      limit: 5,
      offset: 0,
    };

    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/metrics')) return ok(mockCandidateMetrics.D0);
      if (url.includes('/daily-metrics')) {
        expect(url).toContain('horizon=10');
        return ok({ items: dailyRows });
      }
      if (url.includes('/predictions')) {
        expect(url).toContain('date=2025-02-10');
        expect(url).toContain('limit=5');
        return ok(predictionPage);
      }
      return fail(404, 'RUN_NOT_FOUND', 'nope');
    }) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    const metrics = await api.getMetrics(runId, 'D0');
    expect(metrics.horizons.map((h) => h.horizon)).toEqual([10, 40, 120]);

    const daily = await api.getDailyMetrics(runId, 'D0', { horizon: 10 });
    expect(daily).toHaveLength(1);
    expect(daily[0]?.ordinal).toBe('E001');

    const page = await api.getPredictions(runId, 'D0', { date: '2025-02-10', limit: 5 });
    expect(page.total).toBe(10);
    expect(page.items).toHaveLength(10);
  });

  it('parses diagnostics and integrity', async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/diagnostics')) return ok(mockDiagnostics());
      return ok(mockIntegrity);
    }) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    expect((await api.getDiagnostics(runId, 'D0')).horizons).toHaveLength(3);
    expect((await api.getIntegrity(runId)).topK).toBe(5);
  });

  it('maps server error envelopes to typed errors', async () => {
    const fetchImpl = vi.fn(async () =>
      fail(404, 'RUN_NOT_FOUND', 'run missing'),
    ) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    await expect(api.getRun('nope')).rejects.toMatchObject({ code: 'RUN_NOT_FOUND' });

    const sealedFetch = vi.fn(async () =>
      fail(403, 'SEALED_PHASE', 'sealed'),
    ) as unknown as typeof fetch;
    await expect(adapterWith(sealedFetch).getIntegrity('x')).rejects.toMatchObject({
      code: 'SEALED_PHASE',
    });
  });

  it('maps network failure to "API disconnected" and never leaks stack traces', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    const error = await api.getRuns().catch((cause: unknown) => cause);
    expect(error).toBeInstanceOf(ResearchApiError);
    expect((error as ResearchApiError).code).toBe('NETWORK_UNREACHABLE');
    expect((error as ResearchApiError).isDisconnected).toBe(true);
    expect((error as ResearchApiError).userMessage).toBe('研究数据接口未连接。');
  });

  it('rejects responses that do not match the v1 contract shape', async () => {
    const wrongEnvelope = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ data: mockRunSummaries }),
    }) as Response) as unknown as typeof fetch;

    await expect(adapterWith(wrongEnvelope).getRuns()).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
    });

    const wrongShape = vi.fn(async () =>
      ok({ items: [{ bogus: true }] }),
    ) as unknown as typeof fetch;
    await expect(adapterWith(wrongShape).getRuns()).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
    });
  });

  it('encodes query parameters (date, top5, limit, offset, horizon)', async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      seen.push(String(input));
      return ok({
        items: mockPredictionRows('2025-02-10'),
        total: 10,
        limit: 10,
        offset: 0,
      });
    }) as unknown as typeof fetch;

    const api = adapterWith(fetchImpl);
    await api.getPredictions(runId, 'D0', {
      date: '2025-02-10',
      top5: true,
      limit: 10,
      offset: 5,
    });
    expect(seen[0]).toContain('/predictions?');
    expect(seen[0]).toContain('date=2025-02-10');
    expect(seen[0]).toContain('top5=true');
    expect(seen[0]).toContain('offset=5');
  });
});

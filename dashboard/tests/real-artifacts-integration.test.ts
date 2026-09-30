import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { createRealApiAdapter } from '@/api/adapters/real-api';
import { formatReturn, formatUnitless } from '@/lib/format';

const baseUrl = process.env.RESEARCH_DASHBOARD_REAL_API_BASE_URL;
const reportRoot = process.env.RESEARCH_REPORT_ROOT;

describe.skipIf(!baseUrl || !reportRoot)('real Development artifact → HTTP API → dashboard adapter', () => {
  const api = createRealApiAdapter({ baseUrl: baseUrl ?? '' });

  it('validates the live v1 endpoints and exact D0–D3 comparison/integrity fields', async () => {
    expect(await api.getHealth()).toMatchObject({ status: 'ok', readOnly: true });
    expect(await api.getCapabilities()).toMatchObject({ portfolio: false, execution: false,
      validationAvailable: false, finalOosAvailable: false });
    expect(await api.getResearchStatus()).toMatchObject({ phase: 'DEVELOPMENT',
      validation: 'SEALED', finalOos: 'SEALED', strictPit: false,
      executable: false, tradable: false, classification: 'FIXED_CLASSIFICATION_RESEARCH' });
    const runs = await api.getRuns();
    const runId = runs[0]!.runId;
    const runDir = join(reportRoot!, 'shenwan_sector_index', runId);
    const metadata = JSON.parse(await readFile(join(runDir, 'metadata.json'), 'utf8'));
    const summary = JSON.parse(await readFile(join(runDir, 'candidate_summary.json'), 'utf8'));
    const detail = await api.getRun(runId);
    const integrity = await api.getIntegrity(runId);
    expect(detail.candidateIds).toEqual(['D0', 'D1', 'D2', 'D3']);
    expect(detail.syntheticPortfolioConfigHash).toBeNull();
    expect(integrity.gitCommit).toBe(metadata.git_head);
    expect(integrity.protocolHash).toBe(metadata.development_iteration1_protocol_hash);
    expect(integrity.sectorSnapshotId).toBe(metadata.sector_snapshot_id);
    expect(integrity.tradable).toBe(false);
    const candidates = await api.getCandidates(runId);
    expect(candidates.map((candidate) => candidate.candidateId)).toEqual(['D0', 'D1', 'D2', 'D3']);
    for (const candidate of candidates) {
      const row = summary.comparison.find((item: { candidate: string }) =>
        item.candidate === candidate.candidateId);
      const metrics = await api.getMetrics(runId, candidate.candidateId);
      expect(candidate.weightedRankIc).toBe(row.Weighted_RankIC);
      expect(candidate.weightedSpread).toBe(row.Weighted_Spread);
      expect(candidate.promotionStatus).toBe(row.promotion_status.replace(' ', '_'));
      expect(metrics.weightedRankIc).toBe(row.Weighted_RankIC);
      expect(metrics.weightedSpread).toBe(row.Weighted_Spread);
      expect(metrics.horizons.map((h) => h.horizon)).toEqual([10, 40, 120]);
      expect(formatUnitless(candidate.weightedRankIc)).not.toContain('%');
      expect(formatReturn(candidate.weightedSpread)).toContain('%');
      expect((await api.getDiagnostics(runId, candidate.candidateId)).horizons).toHaveLength(3);
    }
  }, 30_000);

  it('accepts live daily/prediction rows across three dates and two candidates without recomputing ranks', async () => {
    const runId = (await api.getRuns())[0]!.runId;
    for (const candidate of ['D0', 'D3']) {
      const daily = await api.getDailyMetrics(runId, candidate, { horizon: 10 });
      expect(daily).toHaveLength(100);
      const dates = [daily[0]!.signalDate, daily[49]!.signalDate, daily[99]!.signalDate];
      for (const horizon of [10, 40, 120] as const) {
        const rows = await api.getDailyMetrics(runId, candidate, { horizon });
        expect(rows.map((row) => row.signalDate)).toEqual(daily.map((row) => row.signalDate));
        expect(rows).toHaveLength(100);
      }
      for (const date of dates) {
        const page = await api.getPredictions(runId, candidate, { date });
        expect(page.total).toBe(124);
        expect(page.items).toHaveLength(124);
        expect(page.items.filter((row) => row.top5)).toHaveLength(5);
        expect(page.items.filter((row) => row.top5).map((row) => row.fusedRank))
          .toEqual([1, 2, 3, 4, 5]);
        expect(page.items.slice(0, 10).every((row) => /^\d{6}$/.test(row.sectorCode)
          && row.sectorName !== null && row.pred10 !== null
          && row.pred40 !== null && row.pred120 !== null)).toBe(true);
      }
    }
  }, 30_000);

  it('has deterministic live JSON and a sealed-phase error', async () => {
    const runId = (await api.getRuns())[0]!.runId;
    const url = `${baseUrl}/runs/${runId}/integrity`;
    const first = await fetch(url).then((response) => response.text());
    const second = await fetch(url).then((response) => response.text());
    expect(second).toBe(first);
    expect(first).not.toContain(reportRoot!);
    await expect(api.getRun('validation')).rejects.toMatchObject({ code: 'SEALED_PHASE' });
  }, 30_000);
});

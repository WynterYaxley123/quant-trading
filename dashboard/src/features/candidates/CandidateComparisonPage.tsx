import { useMemo } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { getResearchApi } from '@/api';
import type { CandidateMetrics, CandidateSummary, Horizon } from '@/api/contracts';
import { useAppData } from '@/app/AppDataProvider';
import { GroupedBarChart } from '@/components/charts/GroupedBarChart';
import { FilterBar, RunFilter } from '@/components/research/FilterBar';
import { PageHeader } from '@/components/research/PageHeader';
import { PromotionBadge } from '@/components/research/StatusBadges';
import { UnitHint } from '@/components/research/UnitHint';
import { DataTable } from '@/components/tables/DataTable';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states';
import { useResource } from '@/hooks/useResource';
import { formatReturn, formatUnitless } from '@/lib/format';

/**
 * Candidate Comparison — the core D0/D1/D2/D3 comparison page.
 *
 * IMPORTANT: promotion is displayed exactly as reported by the API. The
 * dashboard never re-derives promotion rules, even though they are known.
 */

interface ComparisonRow {
  candidateId: string;
  weightedRankIc: number | null;
  weightedSpread: number | null;
  rankIc10: number | null;
  rankIc40: number | null;
  rankIc120: number | null;
  spread10: number | null;
  spread40: number | null;
  spread120: number | null;
  promotionStatus: CandidateSummary['promotionStatus'];
}

function horizonValue(
  metrics: CandidateMetrics,
  horizon: Horizon,
  field: 'rankIc' | 'top5MinusUniverse',
): number | null {
  return metrics.horizons.find((h) => h.horizon === horizon)?.[field]?.mean ?? null;
}

export function CandidateComparisonPage() {
  const search = useSearch({ strict: false }) as { run?: string };
  const navigate = useNavigate({ from: '/candidates' });
  const { runs, capabilities } = useAppData();
  const api = getResearchApi();

  const runId = search.run ?? runs[0]?.runId ?? '';

  const comparison = useResource(async (signal) => {
    if (!runId) return { candidates: [] as CandidateSummary[], metrics: [] as CandidateMetrics[] };
    const candidates = await api.getCandidates(runId, signal);
    const metrics = await Promise.all(
      candidates.map((candidate) => api.getMetrics(runId, candidate.candidateId, signal)),
    );
    return { candidates, metrics };
  }, [api, runId]);

  const rows: ComparisonRow[] = useMemo(() => {
    const byId = new Map(comparison.data?.metrics.map((m) => [m.candidateId, m]) ?? []);
    return (comparison.data?.candidates ?? []).map((candidate) => {
      const metrics = byId.get(candidate.candidateId);
      return {
        candidateId: candidate.candidateId,
        weightedRankIc: candidate.weightedRankIc,
        weightedSpread: candidate.weightedSpread,
        rankIc10: metrics ? horizonValue(metrics, 10, 'rankIc') : null,
        rankIc40: metrics ? horizonValue(metrics, 40, 'rankIc') : null,
        rankIc120: metrics ? horizonValue(metrics, 120, 'rankIc') : null,
        spread10: metrics ? horizonValue(metrics, 10, 'top5MinusUniverse') : null,
        spread40: metrics ? horizonValue(metrics, 40, 'top5MinusUniverse') : null,
        spread120: metrics ? horizonValue(metrics, 120, 'top5MinusUniverse') : null,
        promotionStatus: candidate.promotionStatus,
      };
    });
  }, [comparison.data]);

  const columns = useMemo<ColumnDef<ComparisonRow>[]>(
    () => [
      { accessorKey: 'candidateId', header: 'Candidate', enableSorting: false },
      {
        id: 'weightedRankIc',
        accessorFn: (row) => row.weightedRankIc ?? undefined,
        header: () => <UnitHint metricKey="weightedRankIc">Weighted RankIC</UnitHint>,
        cell: ({ row }) => formatUnitless(row.original.weightedRankIc),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'weightedSpread',
        accessorFn: (row) => row.weightedSpread ?? undefined,
        header: () => <UnitHint metricKey="weightedSpread">Weighted Spread</UnitHint>,
        cell: ({ row }) => formatReturn(row.original.weightedSpread),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'rankIc10',
        accessorFn: (row) => row.rankIc10 ?? undefined,
        header: 'RankIC 10',
        cell: ({ row }) => formatUnitless(row.original.rankIc10),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'rankIc40',
        accessorFn: (row) => row.rankIc40 ?? undefined,
        header: 'RankIC 40',
        cell: ({ row }) => formatUnitless(row.original.rankIc40),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'rankIc120',
        accessorFn: (row) => row.rankIc120 ?? undefined,
        header: 'RankIC 120',
        cell: ({ row }) => formatUnitless(row.original.rankIc120),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'spread10',
        accessorFn: (row) => row.spread10 ?? undefined,
        header: 'Spread 10',
        cell: ({ row }) => formatReturn(row.original.spread10),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'spread40',
        accessorFn: (row) => row.spread40 ?? undefined,
        header: 'Spread 40',
        cell: ({ row }) => formatReturn(row.original.spread40),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'spread120',
        accessorFn: (row) => row.spread120 ?? undefined,
        header: 'Spread 120',
        cell: ({ row }) => formatReturn(row.original.spread120),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        accessorKey: 'promotionStatus',
        header: 'Promotion',
        enableSorting: false,
        cell: ({ row }) => <PromotionBadge status={row.original.promotionStatus} />,
      },
    ],
    [],
  );

  const initialSorting: SortingState = [{ id: 'weightedRankIc', desc: true }];

  if (capabilities && !capabilities.candidateComparison) {
    return (
      <EmptyState
        title="Candidate comparison unavailable"
        description="The Research API capabilities report that candidate comparison data is not available."
      />
    );
  }

  const categories = rows.map((row) => row.candidateId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Candidate comparison"
        description="Compares development candidates D0–D3 on weighted RankIC (unitless) and weighted spread (return). Promotion status is displayed exactly as reported by the official results — the dashboard never re-derives promotion."
      />

      <FilterBar>
        <RunFilter
          runs={runs}
          value={runId}
          onChange={(next) => void navigate({ search: (prev) => ({ ...prev, run: next }), replace: true })}
        />
      </FilterBar>

      {comparison.loading ? (
        <LoadingState label="Loading candidate comparison" />
      ) : comparison.error ? (
        <ErrorState error={comparison.error} onRetry={comparison.retry} />
      ) : rows.length === 0 ? (
        <EmptyState description="No candidates found for the selected run." />
      ) : (
        <>
          <section aria-label="Weighted metrics" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <GroupedBarChart
              title="Weighted RankIC (unitless)"
              description="Unitless correlation-style metric, 4-decimal display."
              summary={`Bar chart of weighted RankIC by candidate: ${rows
                .map((row) => `${row.candidateId} ${formatUnitless(row.weightedRankIc)}`)
                .join(', ')}.`}
              series={[{ key: 'weightedRankIc', label: 'Weighted RankIC' }]}
              data={rows.map((row) => ({
                category: row.candidateId,
                weightedRankIc: row.weightedRankIc,
              }))}
              valueKind="unitless"
            />
            <GroupedBarChart
              title="Weighted Spread (return)"
              description="Return metric — API decimals displayed as percentages (0.0181 → 1.81%)."
              summary={`Bar chart of weighted spread by candidate: ${rows
                .map((row) => `${row.candidateId} ${formatReturn(row.weightedSpread)}`)
                .join(', ')}.`}
              series={[{ key: 'weightedSpread', label: 'Weighted Spread' }]}
              data={rows.map((row) => ({
                category: row.candidateId,
                weightedSpread: row.weightedSpread,
              }))}
              valueKind="return"
            />
          </section>

          <section aria-label="Horizon detail" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <GroupedBarChart
              title="RankIC by horizon (mean)"
              description="Mean RankIC per horizon 10 / 40 / 120. Unitless."
              summary={`Bar chart of mean RankIC at horizons 10, 40 and 120 for candidates ${categories.join(', ')}.`}
              series={[
                { key: 'rankIc10', label: 'RankIC 10' },
                { key: 'rankIc40', label: 'RankIC 40' },
                { key: 'rankIc120', label: 'RankIC 120' },
              ]}
              data={rows.map((row) => ({
                category: row.candidateId,
                rankIc10: row.rankIc10,
                rankIc40: row.rankIc40,
                rankIc120: row.rankIc120,
              }))}
              valueKind="unitless"
            />
            <GroupedBarChart
              title="Spread by horizon (mean)"
              description="Mean top5-minus-universe return per horizon 10 / 40 / 120."
              summary={`Bar chart of mean spread at horizons 10, 40 and 120 for candidates ${categories.join(', ')}.`}
              series={[
                { key: 'spread10', label: 'Spread 10' },
                { key: 'spread40', label: 'Spread 40' },
                { key: 'spread120', label: 'Spread 120' },
              ]}
              data={rows.map((row) => ({
                category: row.candidateId,
                spread10: row.spread10,
                spread40: row.spread40,
                spread120: row.spread120,
              }))}
              valueKind="return"
            />
          </section>

          <section aria-label="Comparison table" className="min-w-0">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Horizon detail table
              <span className="ml-2 font-normal normal-case tracking-normal text-muted-foreground">
                (RankIC columns are unitless; Spread columns are returns. “—” means unavailable.)
              </span>
            </h3>
            <DataTable
              columns={columns}
              data={rows}
              initialSorting={initialSorting}
              caption="Candidate comparison metrics with promotion status"
            />
          </section>
        </>
      )}
    </div>
  );
}

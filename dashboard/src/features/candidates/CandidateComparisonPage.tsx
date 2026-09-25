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
      { accessorKey: 'candidateId', header: '候选方案', enableSorting: false },
      {
        id: 'weightedRankIc',
        accessorFn: (row) => row.weightedRankIc ?? undefined,
        header: () => <UnitHint metricKey="weightedRankIc">加权 RankIC</UnitHint>,
        cell: ({ row }) => formatUnitless(row.original.weightedRankIc),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'weightedSpread',
        accessorFn: (row) => row.weightedSpread ?? undefined,
        header: () => <UnitHint metricKey="weightedSpread">加权超额收益差</UnitHint>,
        cell: ({ row }) => formatReturn(row.original.weightedSpread),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'rankIc10',
        accessorFn: (row) => row.rankIc10 ?? undefined,
        header: 'RankIC 10日',
        cell: ({ row }) => formatUnitless(row.original.rankIc10),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'rankIc40',
        accessorFn: (row) => row.rankIc40 ?? undefined,
        header: 'RankIC 40日',
        cell: ({ row }) => formatUnitless(row.original.rankIc40),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'rankIc120',
        accessorFn: (row) => row.rankIc120 ?? undefined,
        header: 'RankIC 120日',
        cell: ({ row }) => formatUnitless(row.original.rankIc120),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'spread10',
        accessorFn: (row) => row.spread10 ?? undefined,
        header: '超额收益差 10日',
        cell: ({ row }) => formatReturn(row.original.spread10),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'spread40',
        accessorFn: (row) => row.spread40 ?? undefined,
        header: '超额收益差 40日',
        cell: ({ row }) => formatReturn(row.original.spread40),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'spread120',
        accessorFn: (row) => row.spread120 ?? undefined,
        header: '超额收益差 120日',
        cell: ({ row }) => formatReturn(row.original.spread120),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        accessorKey: 'promotionStatus',
        header: '晋级状态',
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
        title="候选方案对比不可用"
        description="研究数据接口当前未提供候选方案对比。"
      />
    );
  }

  const categories = rows.map((row) => row.candidateId);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="候选方案对比"
        description="对比 Development（开发集）D0–D3 的加权 RankIC（无量纲）与加权超额收益差（收益率）。晋级状态直接来自正式结果，不由界面重新判断。"
      />

      <FilterBar>
        <RunFilter
          runs={runs}
          value={runId}
          onChange={(next) => void navigate({ search: (prev) => ({ ...prev, run: next }), replace: true })}
        />
      </FilterBar>

      {comparison.loading ? (
        <LoadingState label="正在加载候选方案对比" />
      ) : comparison.error ? (
        <ErrorState error={comparison.error} onRetry={comparison.retry} />
      ) : rows.length === 0 ? (
        <EmptyState description="所选研究运行没有候选方案。" />
      ) : (
        <>
          <section aria-label="加权指标" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <GroupedBarChart
              title="加权 RankIC（无量纲）"
              description="无量纲相关性指标，按小数显示。"
              summary={`各候选方案的加权 RankIC：${rows
                .map((row) => `${row.candidateId} ${formatUnitless(row.weightedRankIc)}`)
                .join('，')}。`}
              series={[{ key: 'weightedRankIc', label: '加权 RankIC' }]}
              data={rows.map((row) => ({
                category: row.candidateId,
                weightedRankIc: row.weightedRankIc,
              }))}
              valueKind="unitless"
            />
            <GroupedBarChart
              title="加权超额收益差"
              description="API 保留小数，界面显示百分比（0.0181 → 1.81%）。"
              summary={`各候选方案的加权超额收益差：${rows
                .map((row) => `${row.candidateId} ${formatReturn(row.weightedSpread)}`)
                .join('，')}。`}
              series={[{ key: 'weightedSpread', label: '加权超额收益差' }]}
              data={rows.map((row) => ({
                category: row.candidateId,
                weightedSpread: row.weightedSpread,
              }))}
              valueKind="return"
            />
          </section>

          <section aria-label="预测周期明细" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <GroupedBarChart
              title="各周期平均 RankIC"
              description="10日、40日、120日平均 RankIC；无量纲。"
              summary={`候选方案 ${categories.join('、')} 在 10日、40日、120日的平均 RankIC。`}
              series={[
                { key: 'rankIc10', label: 'RankIC 10日' },
                { key: 'rankIc40', label: 'RankIC 40日' },
                { key: 'rankIc120', label: 'RankIC 120日' },
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
              title="各周期平均超额收益差"
              description="10日、40日、120日 Top5 相对行业整体的平均超额。"
              summary={`候选方案 ${categories.join('、')} 在 10日、40日、120日的平均超额收益差。`}
              series={[
                { key: 'spread10', label: '超额收益差 10日' },
                { key: 'spread40', label: '超额收益差 40日' },
                { key: 'spread120', label: '超额收益差 120日' },
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

          <section aria-label="候选方案对比表" className="min-w-0">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              预测周期明细表
              <span className="ml-2 font-normal normal-case tracking-normal text-muted-foreground">
                （RankIC 无量纲；超额收益差按百分比显示；“—”表示暂无数据。）
              </span>
            </h3>
            <DataTable
              columns={columns}
              data={rows}
              initialSorting={initialSorting}
              caption="候选方案指标与晋级状态对比"
            />
          </section>
        </>
      )}
    </div>
  );
}

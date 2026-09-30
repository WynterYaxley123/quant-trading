import { useMemo } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { getResearchApi } from '@/api';
import type { DailyMetric, MetricKey } from '@/api/contracts';
import { useAppData } from '@/app/AppDataProvider';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import {
  CandidateFilter,
  FilterBar,
  HorizonFilter,
  MetricFilter,
  RunFilter,
} from '@/components/research/FilterBar';
import { PageHeader } from '@/components/research/PageHeader';
import { DataTable } from '@/components/tables/DataTable';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states';
import { useResource } from '@/hooks/useResource';
import {
  formatByKind,
  METRIC_KINDS,
  METRIC_LABELS,
  metricUnitDescription,
  NULL_PLACEHOLDER,
} from '@/lib/format';
import { horizonLabel } from '@/lib/labels';

/**
 * Development Explorer — E001…E100 development time series per candidate,
 * metric and horizon. Explorer state lives in the URL (refresh / back /
 * bookmark safe).
 */

const METRIC_OPTIONS: MetricKey[] = [
  'ic',
  'rankIc',
  'top5ForwardReturn',
  'universeForwardReturn',
  'top5MinusUniverse',
];

function parseMetric(value: string | undefined): MetricKey {
  return METRIC_OPTIONS.includes(value as MetricKey) ? (value as MetricKey) : 'rankIc';
}

function parseHorizon(value: string | undefined): 10 | 40 | 120 {
  return value === '40' ? 40 : value === '120' ? 120 : 10;
}

export function DevelopmentExplorerPage() {
  const search = useSearch({ strict: false }) as {
    run?: string;
    candidate?: string;
    metric?: string;
    horizon?: string;
  };
  const navigate = useNavigate({ from: '/development' });
  const { runs, capabilities } = useAppData();
  const api = getResearchApi();

  const runId = search.run ?? runs[0]?.runId ?? '';
  const candidateId = search.candidate ?? 'D0';
  const metric = parseMetric(search.metric);
  const horizon = parseHorizon(search.horizon);

  const setSearch = (patch: { run?: string; candidate?: string; metric?: string; horizon?: string }) =>
    void navigate({
      search: (prev) => ({ ...prev, ...patch }),
      replace: true,
    });

  const series = useResource(
    (signal) =>
      runId ? api.getDailyMetrics(runId, candidateId, { horizon }, signal) : Promise.resolve([]),
    [api, runId, candidateId, horizon],
  );

  const rows = useMemo(() => series.data ?? [], [series.data]);

  const points = useMemo(
    () =>
      rows.map((row) => ({
        ordinal: row.ordinal,
        signalDate: row.signalDate,
        value: row[metric],
      })),
    [rows, metric],
  );

  const columns = useMemo<ColumnDef<DailyMetric>[]>(
    () => [
      { accessorKey: 'ordinal', header: '序号', enableSorting: false },
      { accessorKey: 'signalDate', header: '信号日期' },
      {
        id: 'value',
        header: METRIC_LABELS[metric] ?? metric,
        cell: ({ row }) => formatByKind(metric, row.original[metric]),
        enableSorting: false,
      },
    ],
    [metric],
  );

  if (capabilities && !capabilities.developmentExplorer) {
    return (
      <EmptyState
        title="Development 探索不可用"
        description="研究数据接口当前未提供 Development 指标序列。"
      />
    );
  }

  const metricLabel = METRIC_LABELS[metric] ?? metric;
  const kind = METRIC_KINDS[metric] ?? 'unitless';

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Development 探索"
        description="按信号日期查看 Development（开发集）E001–E100 的指标序列。筛选条件保存在 URL 中，可通过刷新或书签恢复。"
      />

      <FilterBar>
        <RunFilter runs={runs} value={runId} onChange={(run) => setSearch({ run })} />
        <CandidateFilter
          candidateIds={runs[0]?.candidateIds ?? ['D0', 'D1', 'D2', 'D3']}
          value={candidateId}
          onChange={(candidate) => setSearch({ candidate })}
        />
        <MetricFilter value={metric} onChange={(next) => setSearch({ metric: next })} />
        <HorizonFilter value={String(horizon)} onChange={(next) => setSearch({ horizon: next })} />
      </FilterBar>

      {series.loading ? (
        <LoadingState label="正在加载 Development 指标序列" />
      ) : series.error ? (
        <ErrorState error={series.error} onRetry={series.retry} />
      ) : rows.length === 0 ? (
        <EmptyState description="当前筛选条件下没有 Development 指标。" />
      ) : (
        <>
          <TimeSeriesChart
            title={`${metricLabel} · ${horizonLabel(horizon)}（${kind === 'return' ? '收益率' : '无量纲'}）`}
            description={metricUnitDescription(metric)}
            summary={`候选方案 ${candidateId} 的 ${horizonLabel(horizon)} ${metricLabel}，共 ${points.length} 个信号日期：${points[0]?.signalDate} 至 ${points[points.length - 1]?.signalDate}。`}
            points={points}
            valueKind={kind}
            showZeroLine
          />

          <section aria-label="指标序列数值" className="min-w-0">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              指标序列数值
              <span className="ml-2 font-normal normal-case tracking-normal">
                {metricUnitDescription(metric)}
              </span>
            </h3>
            <DataTable
              columns={columns}
              data={rows}
              caption={`Development ${horizonLabel(horizon)} ${metricLabel} 指标序列`}
            />
          </section>
        </>
      )}
      <p className="text-xs text-muted-foreground">
        缺失值显示为 {NULL_PLACEHOLDER}。Top5 未来收益是研究标签指标，不是策略或组合收益。
      </p>
    </div>
  );
}

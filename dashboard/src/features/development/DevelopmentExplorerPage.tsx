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
      { accessorKey: 'ordinal', header: 'Ordinal', enableSorting: false },
      { accessorKey: 'signalDate', header: 'Signal date' },
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
        title="Development explorer unavailable"
        description="The Research API capabilities report that development explorer data is not available."
      />
    );
  }

  const metricLabel = METRIC_LABELS[metric] ?? metric;
  const kind = METRIC_KINDS[metric] ?? 'unitless';

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Development explorer"
        description="Development (E001–E100) metric series by signal date. Filter state is stored in the URL so refresh, back, forward and bookmarks restore the same view."
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
        <LoadingState label="Loading development series" />
      ) : series.error ? (
        <ErrorState error={series.error} onRetry={series.retry} />
      ) : rows.length === 0 ? (
        <EmptyState description="No development metrics for the current selection." />
      ) : (
        <>
          <TimeSeriesChart
            title={`${metricLabel} — horizon ${horizon} (${kind === 'return' ? 'return' : 'unitless'})`}
            description={metricUnitDescription(metric)}
            summary={`Line chart of ${metricLabel} at horizon ${horizon} for candidate ${candidateId} across ${points.length} signal dates from ${points[0]?.signalDate} to ${points[points.length - 1]?.signalDate}.`}
            points={points}
            valueKind={kind}
            showZeroLine
          />

          <section aria-label="Series values" className="min-w-0">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Series values
              <span className="ml-2 font-normal normal-case tracking-normal">
                {metricUnitDescription(metric)}
              </span>
            </h3>
            <DataTable
              columns={columns}
              data={rows}
              caption={`Development series values for ${metricLabel} at horizon ${horizon}`}
            />
          </section>
        </>
      )}
      <p className="text-xs text-muted-foreground">
        Missing values render as {NULL_PLACEHOLDER}. Top5 Forward Return is a research label metric —
        it is not a strategy return.
      </p>
    </div>
  );
}

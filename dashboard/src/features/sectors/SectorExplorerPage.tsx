import { useMemo, useState } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { getResearchApi } from '@/api';
import type { Prediction } from '@/api/contracts';
import { useAppData } from '@/app/AppDataProvider';
import { PageHeader } from '@/components/research/PageHeader';
import {
  CandidateFilter,
  DateFilter,
  FilterBar,
  RunFilter,
} from '@/components/research/FilterBar';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states';
import { DataTable } from '@/components/tables/DataTable';
import { useResource } from '@/hooks/useResource';
import { formatReturn, formatUnitless, NULL_PLACEHOLDER } from '@/lib/format';

/**
 * Sector Explorer — one signal date's cross-sectional prediction table
 * (one row per sector, ~124 rows). Rows open a detail panel. Predictions
 * are model outputs — they are NOT realized returns and NOT trade signals.
 */

export function SectorExplorerPage() {
  const search = useSearch({ strict: false }) as {
    run?: string;
    candidate?: string;
    date?: string;
  };
  const navigate = useNavigate({ from: '/sectors' });
  const { runs, capabilities } = useAppData();
  const api = getResearchApi();
  const [selected, setSelected] = useState<Prediction | null>(null);

  const runId = search.run ?? runs[0]?.runId ?? '';
  const candidateId = search.candidate ?? 'D0';

  const setSearch = (patch: { run?: string; candidate?: string; date?: string }) =>
    void navigate({
      search: (prev) => ({ ...prev, ...patch }),
      replace: true,
    });

  // Available signal dates come from the candidate's development metrics —
  // the dashboard never invents dates and never reaches outside the API.
  const dates = useResource(
    async (signal) => {
      if (!runId) return [] as string[];
      const daily = await api.getDailyMetrics(runId, candidateId, undefined, signal);
      return Array.from(new Set(daily.map((row) => row.signalDate))).sort();
    },
    [api, runId, candidateId],
  );

  const dateOptions = useMemo(() => dates.data ?? [], [dates.data]);
  const date = search.date ?? dateOptions[dateOptions.length - 1] ?? '';

  const predictions = useResource(
    (signal) =>
      runId && date
        ? api.getPredictions(runId, candidateId, { date, limit: 500 }, signal)
        : Promise.resolve({ items: [] as Prediction[], total: 0, limit: 0, offset: 0 }),
    [api, runId, candidateId, date],
  );

  const rows = useMemo(() => predictions.data?.items ?? [], [predictions.data]);
  const initialSorting: SortingState = [{ id: 'fusedRank', desc: false }];

  const columns = useMemo<ColumnDef<Prediction>[]>(
    () => [
      {
        id: 'fusedRank',
        accessorFn: (row) => row.fusedRank ?? undefined,
        header: 'Rank',
        cell: ({ row }) => row.original.fusedRank ?? NULL_PLACEHOLDER,
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: false,
      },
      {
        id: 'sectorName',
        accessorFn: (row) => row.sectorName ?? row.sectorCode,
        header: 'Sector',
        cell: ({ row }) => row.original.sectorName ?? row.original.sectorCode,
        sortingFn: 'alphanumeric',
        sortDescFirst: false,
      },
      {
        accessorKey: 'sectorCode',
        header: 'Sector Code',
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.sectorCode}</span>,
      },
      {
        id: 'fusedScore',
        accessorFn: (row) => row.fusedScore ?? undefined,
        header: 'Fused Score',
        cell: ({ row }) => formatUnitless(row.original.fusedScore),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        accessorKey: 'top5',
        header: 'Top5',
        enableSorting: false,
        cell: ({ row }) =>
          row.original.top5 ? (
            <Badge variant="default">Top5</Badge>
          ) : (
            <span className="text-muted-foreground">{NULL_PLACEHOLDER}</span>
          ),
      },
      {
        id: 'pred10',
        accessorFn: (row) => row.pred10 ?? undefined,
        header: 'Pred 10',
        cell: ({ row }) => formatReturn(row.original.pred10),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'pred40',
        accessorFn: (row) => row.pred40 ?? undefined,
        header: 'Pred 40',
        cell: ({ row }) => formatReturn(row.original.pred40),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'pred120',
        accessorFn: (row) => row.pred120 ?? undefined,
        header: 'Pred 120',
        cell: ({ row }) => formatReturn(row.original.pred120),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'realizedForwardReturn10',
        accessorFn: (row) => row.realizedForwardReturn10 ?? undefined,
        header: 'Realized 10',
        cell: ({ row }) => formatReturn(row.original.realizedForwardReturn10),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'realizedForwardReturn40',
        accessorFn: (row) => row.realizedForwardReturn40 ?? undefined,
        header: 'Realized 40',
        cell: ({ row }) => formatReturn(row.original.realizedForwardReturn40),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
      {
        id: 'realizedForwardReturn120',
        accessorFn: (row) => row.realizedForwardReturn120 ?? undefined,
        header: 'Realized 120',
        cell: ({ row }) => formatReturn(row.original.realizedForwardReturn120),
        sortingFn: 'basic',
        sortUndefined: 'last',
        sortDescFirst: true,
      },
    ],
    [],
  );

  if (capabilities && !capabilities.sectorExplorer) {
    return (
      <EmptyState
        title="Sector explorer unavailable"
        description="The Research API capabilities report that sector prediction data is not available."
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Sector explorer"
        description="Cross-sectional predictions for one signal date — one row per sector. Predictions are model outputs and are not realized returns, not trade signals (no buy/sell semantics)."
      />

      <FilterBar>
        <RunFilter runs={runs} value={runId} onChange={(run) => setSearch({ run })} />
        <CandidateFilter
          candidateIds={runs[0]?.candidateIds ?? ['D0', 'D1', 'D2', 'D3']}
          value={candidateId}
          onChange={(candidate) => setSearch({ candidate })}
        />
        <DateFilter dates={dateOptions} value={date} onChange={(next) => setSearch({ date: next })} />
      </FilterBar>

      {dates.loading || predictions.loading ? (
        <LoadingState label="Loading sector predictions" />
      ) : predictions.error ? (
        <ErrorState error={predictions.error} onRetry={predictions.retry} />
      ) : rows.length === 0 ? (
        <EmptyState description="No sector predictions for the selected date." />
      ) : (
        <section aria-label="Sector predictions" className="min-w-0">
          <DataTable
            columns={columns}
            data={rows}
            initialSorting={initialSorting}
            caption={`Sector predictions for ${date} — ${rows.length} rows`}
            onRowClick={(row) => setSelected(row)}
            rowClassName={(row) => (row.original.top5 ? 'bg-primary/5' : undefined)}
          />
        </section>
      )}

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent side="right" aria-label="Sector prediction detail">
          {selected ? (
            <>
              <DialogHeader>
                <DialogTitle>{selected.sectorName ?? selected.sectorCode}</DialogTitle>
                <DialogDescription>
                  {selected.sectorName ? `Sector code ${selected.sectorCode} · ` : ''}
                  signal date {selected.signalDate} · ordinal {selected.ordinal}
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-4 overflow-y-auto px-6 pb-6 text-sm">
                <dl className="grid grid-cols-2 gap-2">
                  <dt className="text-muted-foreground">Fused score</dt>
                  <dd className="text-right font-mono">{formatUnitless(selected.fusedScore)}</dd>
                  <dt className="text-muted-foreground">Fused rank</dt>
                  <dd className="text-right font-mono">{selected.fusedRank ?? NULL_PLACEHOLDER}</dd>
                  <dt className="text-muted-foreground">Top5</dt>
                  <dd className="text-right">
                    {selected.top5 ? <Badge variant="default">Top5</Badge> : NULL_PLACEHOLDER}
                  </dd>
                </dl>

                <section>
                  <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Predictions (model output)
                  </h4>
                  <dl className="grid grid-cols-2 gap-2">
                    <dt className="text-muted-foreground">Pred 10</dt>
                    <dd className="text-right font-mono">{formatReturn(selected.pred10)}</dd>
                    <dt className="text-muted-foreground">Pred 40</dt>
                    <dd className="text-right font-mono">{formatReturn(selected.pred40)}</dd>
                    <dt className="text-muted-foreground">Pred 120</dt>
                    <dd className="text-right font-mono">{formatReturn(selected.pred120)}</dd>
                  </dl>
                </section>

                <section>
                  <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Realized forward returns
                  </h4>
                  <dl className="grid grid-cols-2 gap-2">
                    <dt className="text-muted-foreground">
                      Realized 10 {selected.labelEnd10 ? `(to ${selected.labelEnd10})` : ''}
                    </dt>
                    <dd className="text-right font-mono">
                      {formatReturn(selected.realizedForwardReturn10)}
                    </dd>
                    <dt className="text-muted-foreground">
                      Realized 40 {selected.labelEnd40 ? `(to ${selected.labelEnd40})` : ''}
                    </dt>
                    <dd className="text-right font-mono">
                      {formatReturn(selected.realizedForwardReturn40)}
                    </dd>
                    <dt className="text-muted-foreground">
                      Realized 120 {selected.labelEnd120 ? `(to ${selected.labelEnd120})` : ''}
                    </dt>
                    <dd className="text-right font-mono">
                      {formatReturn(selected.realizedForwardReturn120)}
                    </dd>
                  </dl>
                </section>

                <p className="rounded-md border border-border bg-muted/50 p-3 text-xs text-muted-foreground">
                  Prediction ≠ realized return. Prediction values are model outputs at the signal
                  date; realized values are measured labels ending at the dates listed above. This
                  dashboard assigns no buy/sell meaning to any value.
                </p>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

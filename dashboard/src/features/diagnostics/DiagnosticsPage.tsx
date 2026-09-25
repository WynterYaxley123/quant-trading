import { useNavigate, useSearch } from '@tanstack/react-router';
import { ChevronDown, ChevronRight, TriangleAlert } from 'lucide-react';
import { getResearchApi } from '@/api';
import type { HorizonDiagnostics } from '@/api/contracts';
import { useAppData } from '@/app/AppDataProvider';
import {
  CandidateFilter,
  FilterBar,
  RunFilter,
} from '@/components/research/FilterBar';
import { HashText } from '@/components/research/HashText';
import { PageHeader } from '@/components/research/PageHeader';
import { StatusCard, StatusCardGrid } from '@/components/research/StatusCard';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states';
import { useResource } from '@/hooks/useResource';
import { formatCount, formatUnitless, NULL_PLACEHOLDER } from '@/lib/format';

/**
 * Diagnostics — training/label pipeline health in plain language. Real
 * warnings are never hidden; counts above zero are surfaced as text+icon
 * markers (never colour alone).
 */

function IssueRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | null;
  hint?: string;
}) {
  const flagged = value !== null && value > 0;
  return (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <div>
        <p className="flex items-center gap-1.5 text-sm">
          {flagged ? <TriangleAlert aria-hidden="true" className="h-4 w-4 text-warning" /> : null}
          <span>{label}</span>
          {flagged ? <Badge variant="warning">{formatCount(value)} affected</Badge> : null}
        </p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      <span className="font-mono text-sm">{formatCount(value)}</span>
    </div>
  );
}

function HorizonSection({ entry }: { entry: HorizonDiagnostics }) {
  const zeroStdNote =
    entry.horizon === 10 || entry.horizon === 40
      ? 'Relevant for D1/D3 (train-only standardization): occurrences of zero-std features in the scaler window.'
      : 'Zero-std feature occurrences in the scaler window (relevant for D1/D3).';
  const demeanNote =
    'Relevant for D2/D3 (cross-sectional excess target): max |mean| of demeaned residuals.';

  return (
    <Collapsible defaultOpen={false}>
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">Horizon {entry.horizon}</CardTitle>
          <CollapsibleTrigger className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground">
            Details
            <ChevronDown aria-hidden="true" className="h-4 w-4" />
          </CollapsibleTrigger>
        </CardHeader>
        <CardContent className="flex flex-col divide-y divide-border">
          <dl className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-3">
            <div className="flex justify-between gap-2 sm:flex-col sm:gap-0">
              <dt className="text-muted-foreground">Training observations</dt>
              <dd className="font-mono">{formatCount(entry.trainingObservations)}</dd>
            </div>
            <div className="flex justify-between gap-2 sm:flex-col sm:gap-0">
              <dt className="text-muted-foreground">Valid training dates</dt>
              <dd className="font-mono">{formatCount(entry.validTrainingDates)}</dd>
            </div>
            <div className="flex justify-between gap-2 sm:flex-col sm:gap-0">
              <dt className="text-muted-foreground">Valid sector count</dt>
              <dd className="font-mono">{formatCount(entry.validSectorCounts)}</dd>
            </div>
          </dl>

          <CollapsibleContent className="pt-2">
            <div className="flex flex-col divide-y divide-border">
              <IssueRow
                label="Missing factor exclusions"
                value={entry.missingFactorExclusions}
                hint="Rows excluded because factor inputs were missing."
              />
              <IssueRow
                label="Missing label exclusions"
                value={entry.missingLabelExclusions}
                hint="Rows excluded because the forward-return label was missing for this horizon."
              />
              <IssueRow
                label="Numerical failures"
                value={entry.numericalFailures}
                hint="Training/solve attempts that failed numerically."
              />
              <IssueRow
                label="Insufficient training cases"
                value={entry.insufficientTrainingCases}
                hint="Attempts skipped because too little training data was available."
              />
              <IssueRow
                label="Zero-std feature occurrences"
                value={entry.zeroStdFeatureOccurrences}
                hint={zeroStdNote}
              />
              <div className="flex items-start justify-between gap-3 py-1.5">
                <div>
                  <p className="text-sm">Scaler diagnostic hash</p>
                  <p className="text-xs text-muted-foreground">{demeanNote}</p>
                </div>
                <HashText value={entry.scalerDiagnosticHash} />
              </div>
              <div className="flex items-center justify-between gap-3 py-1.5">
                <span className="text-sm">Demean residual max |mean|</span>
                <span className="font-mono text-sm">
                  {entry.demeanResidualMaxAbsMean === null
                    ? NULL_PLACEHOLDER
                    : formatUnitless(entry.demeanResidualMaxAbsMean)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3 py-1.5">
                <span className="text-sm">Target diagnostic hash</span>
                <HashText value={entry.targetDiagnosticHash} />
              </div>
            </div>
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  );
}

export function DiagnosticsPage() {
  const search = useSearch({ strict: false }) as { run?: string; candidate?: string };
  const navigate = useNavigate({ from: '/diagnostics' });
  const { runs, capabilities } = useAppData();
  const api = getResearchApi();

  const runId = search.run ?? runs[0]?.runId ?? '';
  const candidateId = search.candidate ?? 'D0';

  const setSearch = (patch: { run?: string; candidate?: string }) =>
    void navigate({
      search: (prev) => ({ ...prev, ...patch }),
      replace: true,
    });

  const diagnostics = useResource(
    (signal) => (runId ? api.getDiagnostics(runId, candidateId, signal) : Promise.resolve(null)),
    [api, runId, candidateId],
  );

  if (capabilities && !capabilities.diagnostics) {
    return (
      <EmptyState
        title="Diagnostics unavailable"
        description="The Research API capabilities report that diagnostics data is not available."
      />
    );
  }

  const data = diagnostics.data;
  const issueTotal = (data?.horizons ?? []).reduce(
    (sum, entry) =>
      sum +
      (entry.missingFactorExclusions ?? 0) +
      (entry.missingLabelExclusions ?? 0) +
      (entry.numericalFailures ?? 0) +
      (entry.insufficientTrainingCases ?? 0) +
      (entry.zeroStdFeatureOccurrences ?? 0),
    0,
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Diagnostics"
        description="Training and label pipeline health for the selected candidate. Everything here is informational research diagnostics — no values are hidden, and every count above zero is surfaced."
      />

      <FilterBar>
        <RunFilter runs={runs} value={runId} onChange={(run) => setSearch({ run })} />
        <CandidateFilter
          candidateIds={runs[0]?.candidateIds ?? ['D0', 'D1', 'D2', 'D3']}
          value={candidateId}
          onChange={(candidate) => setSearch({ candidate })}
        />
      </FilterBar>

      {diagnostics.loading ? (
        <LoadingState label="Loading diagnostics" />
      ) : diagnostics.error ? (
        <ErrorState error={diagnostics.error} onRetry={diagnostics.retry} />
      ) : !data ? (
        <EmptyState description="No diagnostics for the current selection." />
      ) : (
        <>
          <section aria-label="Attempt summary">
            <StatusCardGrid>
              <StatusCard label="Attempted dates" value={formatCount(data.attemptedDates)} />
              <StatusCard label="Successful dates" value={formatCount(data.successfulDates)} />
              <StatusCard label="Skipped dates" value={formatCount(data.skippedDates)} />
              <StatusCard
                label="Issue summary"
                value={issueTotal > 0 ? `${formatCount(issueTotal)} flagged` : 'No issues flagged'}
                hint="Aggregate exclusions / failures / zero-std occurrences across horizons"
                valueClassName={issueTotal > 0 ? 'text-warning' : undefined}
              />
              <StatusCard
                label="Horizons covered"
                value={data.horizons.map((entry) => entry.horizon).join(' / ') || NULL_PLACEHOLDER}
              />
            </StatusCardGrid>
          </section>

          <section aria-label="Per-horizon diagnostics" className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Per-horizon details
              <span className="ml-2 inline-flex items-center gap-1 font-normal normal-case tracking-normal">
                <ChevronRight aria-hidden="true" className="inline h-3.5 w-3.5" />
                open a horizon to see full issue counts
              </span>
            </h3>
            {data.horizons.map((entry) => (
              <HorizonSection key={entry.horizon} entry={entry} />
            ))}
          </section>
        </>
      )}
    </div>
  );
}

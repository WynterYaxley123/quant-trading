import { getResearchApi } from '@/api';
import type { CandidateSummary, Integrity } from '@/api/contracts';
import { useAppData } from '@/app/AppDataProvider';
import { CandidateCard } from '@/components/research/CandidateCard';
import { HashText } from '@/components/research/HashText';
import { PageHeader } from '@/components/research/PageHeader';
import { StatusCard, StatusCardGrid } from '@/components/research/StatusCard';
import { SealedBadge } from '@/components/research/StatusBadges';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorState, LoadingState } from '@/components/ui/states';
import { useResource } from '@/hooks/useResource';

/**
 * Overview — the 5-second research-state page. It leads with phase / sealing
 * / executability before any metric. Deliberately shows NO profit, equity,
 * Sharpe or drawdown: no official portfolio contract exists yet.
 */
export function OverviewPage() {
  const { status, runs, loading: shellLoading } = useAppData();
  const api = getResearchApi();
  const currentRun = runs[0] ?? null;

  const details = useResource(async (signal) => {
    if (!currentRun) return { candidates: [] as CandidateSummary[], integrity: null as Integrity | null };
    const [candidates, integrity] = await Promise.all([
      api.getCandidates(currentRun.runId, signal),
      api.getIntegrity(currentRun.runId, signal),
    ]);
    return { candidates, integrity };
  }, [api, currentRun?.runId]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Research overview"
        description="Current research state for the Shenwan sector-index research programme. This is a read-only research dashboard — results are development candidates only and are not validated, not executable and not tradable."
      />

      <section aria-label="Research state">
        <StatusCardGrid>
          <StatusCard label="Phase" value={status?.phase ?? '—'} hint="Active research phase" />
          <StatusCard
            label="Validation"
            value={status ? <SealedBadge label={status.validation} /> : '—'}
            hint="Sealed — no unlock or preview exists"
          />
          <StatusCard
            label="Final OOS"
            value={status ? <SealedBadge label={status.finalOos} /> : '—'}
            hint="Sealed — no unlock or preview exists"
          />
          <StatusCard
            label="Executable"
            value={status ? (status.executable ? 'YES' : 'NO') : '—'}
            hint="Whether results can be executed"
          />
          <StatusCard
            label="Tradable"
            value={status ? (status.tradable ? 'YES' : 'NO') : '—'}
            hint="Whether anything can be traded"
          />
        </StatusCardGrid>
      </section>

      <section aria-label="Candidate summary" className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Candidate summary
        </h3>
        {shellLoading || details.loading ? (
          <LoadingState label="Loading candidates" />
        ) : details.error ? (
          <ErrorState error={details.error} onRetry={details.retry} />
        ) : details.data && details.data.candidates.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {details.data.candidates.map((candidate) => (
              <CandidateCard key={candidate.candidateId} candidate={candidate} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No candidates found for the current run.</p>
        )}
      </section>

      <section aria-label="Current run and protocol" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Current run</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Run ID</span>
              <span className="min-w-0 break-all text-right font-mono text-xs">
                {currentRun?.runId ?? '—'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Git commit</span>
              <HashText value={currentRun?.gitCommit} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Protocol hash</span>
              <HashText value={currentRun?.protocolHash} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Sector snapshot</span>
              <HashText value={currentRun?.sectorSnapshotId} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Research configuration</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            {details.data?.integrity ? (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Universe</span>
                  <span>
                    {details.data.integrity.universe} ({details.data.integrity.sectorCount} sectors)
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Features</span>
                  <span>{details.data.integrity.featureCount}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">Horizons</span>
                  <span>{details.data.integrity.horizons.join(' / ')}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">TopK</span>
                  <span>{details.data.integrity.topK}</span>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">—</p>
            )}
            <p className="text-xs text-muted-foreground">
              Full protocol hashes and status flags are on the Research Integrity page.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

import { useNavigate, useSearch } from '@tanstack/react-router';
import { getResearchApi } from '@/api';
import { useAppData } from '@/app/AppDataProvider';
import { FilterBar, RunFilter } from '@/components/research/FilterBar';
import { HashText } from '@/components/research/HashText';
import { PageHeader } from '@/components/research/PageHeader';
import { StatusCard, StatusCardGrid } from '@/components/research/StatusCard';
import { SealedBadge } from '@/components/research/StatusBadges';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/states';
import { useResource } from '@/hooks/useResource';
import { formatCount, formatFactor, NULL_PLACEHOLDER } from '@/lib/format';

/**
 * Research Integrity — the audit page: identity, protocol constants, hashes
 * and status flags exactly as reported by the API artifacts. Hashes are
 * abbreviated by default and expandable on click.
 */

function KeyValue({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-sm">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words text-right">{children}</span>
    </div>
  );
}

export function ResearchIntegrityPage() {
  const search = useSearch({ strict: false }) as { run?: string };
  const navigate = useNavigate({ from: '/integrity' });
  const { runs, status } = useAppData();
  const api = getResearchApi();

  const runId = search.run ?? runs[0]?.runId ?? '';

  const detail = useResource(
    async (signal) => {
      if (!runId) return null;
      const [run, integrity] = await Promise.all([
        api.getRun(runId, signal),
        api.getIntegrity(runId, signal),
      ]);
      return { run, integrity };
    },
    [api, runId],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Research integrity"
        description="Immutable identity of the research run: label, phase, protocol constants and artifact hashes as reported by the official research artifacts. Hashes are abbreviated — click one to reveal its full value."
      />

      <FilterBar>
        <RunFilter
          runs={runs}
          value={runId}
          onChange={(next) => void navigate({ search: (prev) => ({ ...prev, run: next }), replace: true })}
        />
      </FilterBar>

      {detail.loading ? (
        <LoadingState label="Loading integrity record" />
      ) : detail.error ? (
        <ErrorState error={detail.error} onRetry={detail.retry} />
      ) : !detail.data ? (
        <EmptyState description="No integrity record for the selected run." />
      ) : (
        <>
          <section aria-label="Status flags">
            <StatusCardGrid>
              <StatusCard
                label="Development"
                value={detail.data.integrity.phase === 'DEVELOPMENT' ? 'ACTIVE' : detail.data.integrity.phase}
              />
              <StatusCard label="Validation" value={<SealedBadge label={detail.data.integrity.validation} />} />
              <StatusCard label="Final OOS" value={<SealedBadge label={detail.data.integrity.finalOos} />} />
              <StatusCard label="Executable" value={detail.data.integrity.executable ? 'YES' : 'NO'} />
              <StatusCard label="Strict PIT" value={detail.data.integrity.strictPit ? 'YES' : 'NO'} />
            </StatusCardGrid>
            <StatusCardGrid className="mt-3">
              <StatusCard label="ETF" value={detail.data.integrity.etf} />
              <StatusCard label="Synthetic portfolio" value={detail.data.integrity.syntheticPortfolio} />
              <StatusCard label="LEVEL B" value={detail.data.integrity.levelB} />
            </StatusCardGrid>
          </section>

          <section aria-label="Research definition" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Research definition</CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-border">
                <KeyValue label="Research label">
                  {detail.data.integrity.researchLabel}
                </KeyValue>
                <KeyValue label="Phase">{detail.data.integrity.phase}</KeyValue>
                <KeyValue label="Classification admission">
                  {detail.data.run.classificationAdmission}
                </KeyValue>
                <KeyValue label="Universe">
                  {detail.data.integrity.universe} ({formatCount(detail.data.integrity.sectorCount)}{' '}
                  sectors)
                </KeyValue>
                <KeyValue label="Feature count">
                  {formatCount(detail.data.integrity.featureCount)}
                </KeyValue>
                <KeyValue label="Alpha">{formatFactor(detail.data.integrity.alpha)}</KeyValue>
                <KeyValue label="Horizons">
                  {detail.data.integrity.horizons.join(' / ') || NULL_PLACEHOLDER}
                </KeyValue>
                <KeyValue label="Fusion weights">
                  {detail.data.integrity.fusion.map((weight) => formatFactor(weight)).join(' / ') ||
                    NULL_PLACEHOLDER}
                </KeyValue>
                <KeyValue label="TopK">{formatCount(detail.data.integrity.topK)}</KeyValue>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Artifact hashes</CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-border">
                <KeyValue label="Split policy hash">
                  <HashText value={detail.data.integrity.splitPolicyHash} />
                </KeyValue>
                <KeyValue label="Prediction config hash">
                  <HashText value={detail.data.integrity.predictionConfigHash} />
                </KeyValue>
                <KeyValue label="Development iteration-1 protocol hash">
                  <HashText value={detail.data.integrity.developmentIteration1ProtocolHash} />
                </KeyValue>
                <KeyValue label="Sector snapshot ID">
                  <HashText value={detail.data.integrity.sectorSnapshotId} />
                </KeyValue>
                <KeyValue label="Synthetic portfolio config hash">
                  <HashText value={detail.data.run.syntheticPortfolioConfigHash} />
                </KeyValue>
                <KeyValue label="Git commit">
                  <HashText value={detail.data.run.gitCommit} />
                </KeyValue>
                <KeyValue label="Source of truth">
                  {status?.sourceOfTruth ?? 'RESEARCH_ARTIFACTS'}
                </KeyValue>
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}

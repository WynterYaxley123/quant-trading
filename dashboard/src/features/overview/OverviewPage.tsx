import { getResearchApi } from '@/api';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { FilterBar, RunFilter } from '@/components/research/FilterBar';
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
import { classificationLabel, horizonLabel, phaseLabel, yesNo } from '@/lib/labels';

/**
 * Overview — the 5-second research-state page. It leads with phase / sealing
 * / executability before any metric. Deliberately shows NO profit, equity,
 * Sharpe or drawdown: no official portfolio contract exists yet.
 */
export function OverviewPage() {
  const { status, runs, loading: shellLoading } = useAppData();
  const search = useSearch({ strict: false }) as {run?:string};
  const navigate = useNavigate({from:'/research'});
  const api = getResearchApi();
  const currentRun = search.run ? runs.find((run) => run.runId === search.run) ?? null : runs[0] ?? null;

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
        title="概览"
        description="申万行业指数研究的当前状态。这里只展示 Development（开发集）候选结果，尚未经 Validation 验证，不可执行、不可交易。"
      />

      <FilterBar>
        <RunFilter runs={runs} value={currentRun?.runId ?? ''}
          onChange={(run) => void navigate({search:(prev) => ({...prev,run}),replace:true})} />
      </FilterBar>
      {search.run && !currentRun ? <p role="alert">所选运行不在获准的 Development 清单中，请选择一个获准运行。</p> : null}

      <section aria-label="获准 Development 工作区">
        <StatusCardGrid>
          <StatusCard label="研究工作区" value={status?.artifactId ?? 'NOT_AVAILABLE_FOR_THIS_RUN'} />
          <StatusCard label="批准状态" value={status?.approvalState ?? 'NOT_AVAILABLE_FOR_THIS_RUN'} />
          <StatusCard label="获准运行数" value={status?.availableRunCount ?? runs.length} />
          <StatusCard label="完整性" value={status?.integrityStatus ?? 'NOT_AVAILABLE_FOR_THIS_RUN'} />
          <StatusCard label="候选方案" value={status?.candidateAvailability ?? 'NOT_AVAILABLE_FOR_THIS_RUN'} />
          <StatusCard label="Development 指标" value={status?.metricsAvailability ?? 'NOT_AVAILABLE_FOR_THIS_RUN'} />
          <StatusCard label="诊断产物" value={status?.diagnosticsAvailability ?? 'NOT_AVAILABLE_FOR_THIS_RUN'} />
        </StatusCardGrid>
        <p className="mt-3 text-xs text-muted-foreground">DEVELOPMENT ONLY · READ-ONLY · Research U0_FIXED_124 与 ETF Quant 的 107 个准入行业是两个独立范围。</p>
      </section>

      <section aria-label="研究状态">
        <StatusCardGrid>
          <StatusCard label="研究阶段" value={status ? phaseLabel(status.phase) : '—'} />
          <StatusCard
            label="Validation（验证集）"
            value={status ? <SealedBadge label={status.validation} /> : '—'}
            hint="已封存，不提供预览或解封入口"
          />
          <StatusCard
            label="Final OOS（最终样本外）"
            value={status ? <SealedBadge label={status.finalOos} /> : '—'}
            hint="已封存，不提供预览或解封入口"
          />
          <StatusCard
            label="可执行"
            value={status ? yesNo(status.executable) : '—'}
          />
          <StatusCard
            label="可交易"
            value={status ? yesNo(status.tradable) : '—'}
          />
          <StatusCard label="严格 PIT" value={status ? yesNo(status.strictPit) : '—'} />
        </StatusCardGrid>
      </section>

      <section aria-label="候选方案摘要" className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          候选方案摘要
        </h3>
        {shellLoading || details.loading ? (
          <LoadingState label="正在加载候选方案" />
        ) : details.error ? (
          <ErrorState error={details.error} onRetry={details.retry} />
        ) : details.data && details.data.candidates.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {details.data.candidates.map((candidate) => (
              <CandidateCard key={candidate.candidateId} candidate={candidate} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">当前研究运行没有候选方案。</p>
        )}
      </section>

      <section aria-label="当前运行与研究协议" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>当前研究运行</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">运行 ID</span>
              <span className="min-w-0 break-all text-right font-mono text-xs">
                {currentRun?.runId ?? '—'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">Git Commit</span>
              <HashText value={currentRun?.gitCommit} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">研究协议 Hash</span>
              <HashText value={currentRun?.protocolHash} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">行业数据快照 ID</span>
              <HashText value={currentRun?.sectorSnapshotId} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>研究配置</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            {details.data?.integrity ? (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">研究范围</span>
                  <span>
                    {details.data.integrity.universe}（{details.data.integrity.sectorCount} 个行业）
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">因子数</span>
                  <span>{details.data.integrity.featureCount}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">预测周期</span>
                  <span>{details.data.integrity.horizons.map(horizonLabel).join(' / ')}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">TopK</span>
                  <span>{details.data.integrity.topK}</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-muted-foreground">分类方式</span>
                  <span>{classificationLabel(details.data.integrity.classification)}</span>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">—</p>
            )}
            <p className="text-xs text-muted-foreground">
              完整协议 Hash 与状态标记见“研究完整性”页面。
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

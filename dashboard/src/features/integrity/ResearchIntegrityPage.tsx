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
import {
  classificationLabel, enabledLabel, horizonLabel, phaseLabel,
  researchLabel, sourceLabel, yesNo,
} from '@/lib/labels';

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
        title="研究完整性"
        description="展示正式研究产物记录的运行身份、阶段、协议常量和 Hash。Hash 默认缩写，点击可查看完整值。"
      />

      <FilterBar>
        <RunFilter
          runs={runs}
          value={runId}
          onChange={(next) => void navigate({ search: (prev) => ({ ...prev, run: next }), replace: true })}
        />
      </FilterBar>

      {detail.loading ? (
        <LoadingState label="正在加载研究完整性记录" />
      ) : detail.error ? (
        <ErrorState error={detail.error} onRetry={detail.retry} />
      ) : !detail.data ? (
        <EmptyState description="所选运行没有研究完整性记录。" />
      ) : (
        <>
          <section aria-label="研究状态标记">
            <StatusCardGrid>
              <StatusCard
                label="研究阶段"
                value={phaseLabel(detail.data.integrity.phase)}
              />
              <StatusCard label="Validation（验证集）" value={<SealedBadge label={detail.data.integrity.validation} />} />
              <StatusCard label="Final OOS（最终样本外）" value={<SealedBadge label={detail.data.integrity.finalOos} />} />
              <StatusCard label="可执行" value={yesNo(detail.data.integrity.executable)} />
              <StatusCard label="可交易" value={yesNo(detail.data.integrity.tradable)} />
              <StatusCard label="严格 PIT" value={yesNo(detail.data.integrity.strictPit)} />
            </StatusCardGrid>
            <StatusCardGrid className="mt-3">
              <StatusCard label="ETF 执行" value={enabledLabel(detail.data.integrity.etf)} />
              <StatusCard label="合成组合" value={enabledLabel(detail.data.integrity.syntheticPortfolio)} />
              <StatusCard label="LEVEL B" value={enabledLabel(detail.data.integrity.levelB)} />
            </StatusCardGrid>
          </section>

          <section aria-label="研究定义与 Hash" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>研究定义</CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-border">
                <KeyValue label="研究标签">
                  {researchLabel(detail.data.integrity.researchLabel)}
                </KeyValue>
                <KeyValue label="研究阶段">{phaseLabel(detail.data.integrity.phase)}</KeyValue>
                <KeyValue label="分类方式">
                  {classificationLabel(detail.data.integrity.classification)}
                </KeyValue>
                <KeyValue label="研究范围">
                  {detail.data.integrity.universe} ({formatCount(detail.data.integrity.sectorCount)}{' '}
                  个行业)
                </KeyValue>
                <KeyValue label="因子数">
                  {formatCount(detail.data.integrity.featureCount)}
                </KeyValue>
                <KeyValue label="Alpha">{formatFactor(detail.data.integrity.alpha)}</KeyValue>
                <KeyValue label="预测周期">
                  {detail.data.integrity.horizons.map(horizonLabel).join(' / ') || NULL_PLACEHOLDER}
                </KeyValue>
                <KeyValue label="融合权重">
                  {detail.data.integrity.fusion.map((weight) => formatFactor(weight)).join(' / ') ||
                    NULL_PLACEHOLDER}
                </KeyValue>
                <KeyValue label="TopK">{formatCount(detail.data.integrity.topK)}</KeyValue>
                <KeyValue label="运行 ID">{detail.data.run.runId}</KeyValue>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>研究产物 Hash</CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-border">
                <KeyValue label="样本划分策略 Hash">
                  <HashText value={detail.data.integrity.splitPolicyHash} />
                </KeyValue>
                <KeyValue label="预测配置 Hash">
                  <HashText value={detail.data.integrity.predictionConfigHash} />
                </KeyValue>
                <KeyValue label="研究协议 Hash">
                  <HashText value={detail.data.integrity.developmentIteration1ProtocolHash} />
                </KeyValue>
                <KeyValue label="行业数据快照 ID">
                  <HashText value={detail.data.integrity.sectorSnapshotId} />
                </KeyValue>
                <KeyValue label="合成组合配置 Hash">
                  <HashText value={detail.data.integrity.syntheticPortfolioConfigHash} />
                </KeyValue>
                <KeyValue label="Git Commit">
                  <HashText value={detail.data.integrity.gitCommit} />
                </KeyValue>
                <KeyValue label="数据事实来源">
                  {status ? sourceLabel(status.sourceOfTruth) : NULL_PLACEHOLDER}
                </KeyValue>
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}

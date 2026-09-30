import { useNavigate, useSearch } from '@tanstack/react-router';
import { ChevronDown, ChevronRight, TriangleAlert } from 'lucide-react';
import { getResearchApi } from '@/api';
import type { Diagnostics, HorizonDiagnostics } from '@/api/contracts';
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
          {flagged ? <Badge variant="warning">影响 {formatCount(value)} 项</Badge> : null}
        </p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      <span className="font-mono text-sm">{formatCount(value)}</span>
    </div>
  );
}

function formatRange(value: HorizonDiagnostics['trainingObservations']): string {
  if (value.min === null && value.median === null && value.max === null) return NULL_PLACEHOLDER;
  return `${formatCount(value.min)} / ${formatCount(value.median)} / ${formatCount(value.max)}`;
}

function HorizonSection({ entry }: { entry: HorizonDiagnostics }) {
  return (
    <Collapsible defaultOpen={false}>
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">{entry.horizon}日预测周期</CardTitle>
          <CollapsibleTrigger className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground">
            查看明细
            <ChevronDown aria-hidden="true" className="h-4 w-4" />
          </CollapsibleTrigger>
        </CardHeader>
        <CardContent className="flex flex-col divide-y divide-border">
          <p className="mb-2 text-xs text-muted-foreground">以下范围依次为最小值 / 中位数 / 最大值，来自正式训练诊断记录。</p>
          <dl className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-3">
            <div className="flex justify-between gap-2 sm:flex-col sm:gap-0">
              <dt className="text-muted-foreground">训练样本数</dt>
              <dd className="font-mono">{formatRange(entry.trainingObservations)}</dd>
            </div>
            <div className="flex justify-between gap-2 sm:flex-col sm:gap-0">
              <dt className="text-muted-foreground">有效训练日期数</dt>
              <dd className="font-mono">{formatRange(entry.validTrainingDates)}</dd>
            </div>
            <div className="flex justify-between gap-2 sm:flex-col sm:gap-0">
              <dt className="text-muted-foreground">有效行业数</dt>
              <dd className="font-mono">{formatRange(entry.validSectorCounts)}</dd>
            </div>
          </dl>

          <CollapsibleContent className="pt-2">
            <div className="flex flex-col divide-y divide-border">
              <IssueRow
                label="缺失因子剔除数"
                value={entry.missingFactorExclusions}
                hint="因子输入缺失而剔除的记录。"
              />
              <IssueRow
                label="缺失标签剔除数"
                value={entry.missingLabelExclusions}
                hint="该预测周期的未来收益标签缺失而剔除的记录。"
              />
              <IssueRow
                label="数值计算失败数"
                value={entry.numericalFailures}
                hint="训练或求解过程中出现的数值失败。"
              />
              <IssueRow
                label="训练样本不足次数"
                value={entry.insufficientTrainingCases}
                hint="因训练数据不足而跳过的尝试。"
              />
            </div>
          </CollapsibleContent>
        </CardContent>
      </Card>
    </Collapsible>
  );
}

function TransformationSection({ data }: { data: Diagnostics }) {
  return (
    <section aria-label="特征与目标变换诊断">
      <Card>
        <CardHeader><CardTitle className="text-sm">特征与目标变换诊断</CardTitle></CardHeader>
        <CardContent className="flex flex-col divide-y divide-border">
          <IssueRow
            label="零标准差特征次数"
            value={data.zeroStdFeatureOccurrences}
            hint="仅训练集标准化的候选方案适用；未建模时显示“—”。"
          />
          <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
            <span>标准化器诊断 Hash</span>
            <HashText value={data.scalerDiagnosticHash} />
          </div>
          <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
            <span>去均值残差最大绝对均值</span>
            <span className="font-mono">{formatUnitless(data.demeanResidualMaxAbsMean)}</span>
          </div>
          <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
            <span>训练目标诊断 Hash</span>
            <HashText value={data.targetDiagnosticHash} />
          </div>
        </CardContent>
      </Card>
    </section>
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
        title="诊断数据不可用"
        description="研究数据接口当前未提供诊断信息。"
      />
    );
  }

  const data = diagnostics.data;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="诊断"
        description="所选候选方案的训练与标签流程诊断。数值直接来自正式研究产物；不存在的字段保留为“—”，不解释为零。"
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
        <LoadingState label="正在加载诊断信息" />
      ) : diagnostics.error ? (
        <ErrorState error={diagnostics.error} onRetry={diagnostics.retry} />
      ) : !data ? (
        <EmptyState description="当前筛选条件下没有诊断信息。" />
      ) : (
        <>
          <section aria-label="尝试次数摘要">
            <StatusCardGrid>
              <StatusCard label="尝试日期数" value={formatCount(data.attemptedDates)} />
              <StatusCard label="成功日期数" value={formatCount(data.successfulDates)} />
              <StatusCard label="跳过日期数" value={formatCount(data.skippedDates)} />
              <StatusCard
                label="零标准差特征次数"
                value={formatCount(data.zeroStdFeatureOccurrences)}
                hint="仅在正式产物记录该诊断时显示数值"
                valueClassName={data.zeroStdFeatureOccurrences !== null && data.zeroStdFeatureOccurrences > 0 ? 'text-warning' : undefined}
              />
              <StatusCard
                label="覆盖预测周期"
                value={data.horizons.map((entry) => `${entry.horizon}日`).join(' / ') || NULL_PLACEHOLDER}
              />
            </StatusCardGrid>
          </section>

          <section aria-label="各预测周期诊断" className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              各预测周期明细
              <span className="ml-2 inline-flex items-center gap-1 font-normal normal-case tracking-normal">
                <ChevronRight aria-hidden="true" className="inline h-3.5 w-3.5" />
                展开预测周期查看剔除及失败数
              </span>
            </h3>
            {data.horizons.map((entry) => (
              <HorizonSection key={entry.horizon} entry={entry} />
            ))}
          </section>
          <TransformationSection data={data} />
        </>
      )}
    </div>
  );
}

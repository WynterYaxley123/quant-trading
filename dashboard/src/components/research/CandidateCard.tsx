import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PromotionBadge } from './StatusBadges';
import { UnitHint } from './UnitHint';
import type { CandidateSummary } from '@/api/contracts';
import { formatReturn, formatUnitless, NULL_PLACEHOLDER } from '@/lib/format';
import { preprocessingLabel, targetLabel } from '@/lib/labels';

/**
 * Candidate summary card. Values come straight from the API — the dashboard
 * never re-derives metrics or promotion. Units are explicit:
 * Weighted RankIC = unitless, Weighted Spread = return (decimal → %).
 */
export function CandidateCard({ candidate }: { candidate: CandidateSummary }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base font-semibold">{candidate.candidateId}</CardTitle>
        <PromotionBadge status={candidate.promotionStatus} />
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div>
          <UnitHint metricKey="weightedRankIc">
            <span className="text-xs text-muted-foreground">加权 RankIC（无量纲）</span>
          </UnitHint>
          <p className="font-mono text-lg">{formatUnitless(candidate.weightedRankIc)}</p>
        </div>
        <div>
          <UnitHint metricKey="weightedSpread">
            <span className="text-xs text-muted-foreground">加权超额收益差</span>
          </UnitHint>
          <p className="font-mono text-lg">{formatReturn(candidate.weightedSpread)}</p>
        </div>
        <dl className="grid grid-cols-1 gap-1 text-xs text-muted-foreground">
          <div className="flex items-start justify-between gap-2">
            <dt className="shrink-0">X 预处理</dt>
            <dd className="min-w-0 break-words text-right">
              {candidate.xPreprocessing ? preprocessingLabel(candidate.xPreprocessing) : NULL_PLACEHOLDER}
            </dd>
          </div>
          <div className="flex items-start justify-between gap-2">
            <dt className="shrink-0">训练目标</dt>
            <dd className="min-w-0 break-words text-right">
              {candidate.trainingTarget ? targetLabel(candidate.trainingTarget) : NULL_PLACEHOLDER}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

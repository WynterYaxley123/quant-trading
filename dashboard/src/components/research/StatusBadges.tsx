import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import type { PromotionStatus } from '@/api/contracts';
import { sealLabel } from '@/lib/labels';

/** Sealed phase marker. Deliberately not interactive — sealed data has no unlock. */
export function SealedBadge({ label = 'SEALED' }: { label?: string }) {
  return <Badge variant="sealed" title={label}>{sealLabel(label)}</Badge>;
}

/**
 * Promotion status — rendered exactly as reported by the API
 * (`promotionStatus` is the single source of truth; the dashboard never
 * re-derives promotion). Status is text + shape, never colour alone.
 */
export function PromotionBadge({ status }: { status: PromotionStatus }) {
  if (status === 'DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW') {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0}>
            <Badge variant="success">进入进一步研究</Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          正式状态为 DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW，仅表示进入进一步研究；不代表获批、可交易或盈利。
        </TooltipContent>
      </Tooltip>
    );
  }
  if (status === 'NOT_PROMOTED') {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0}>
            <Badge variant="muted">未晋级</Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>正式状态为 NOT_PROMOTED。</TooltipContent>
      </Tooltip>
    );
  }
  return <Badge variant="outline">—</Badge>;
}

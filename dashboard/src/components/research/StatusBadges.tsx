import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import type { PromotionStatus } from '@/api/contracts';

/** Sealed phase marker. Deliberately not interactive — sealed data has no unlock. */
export function SealedBadge({ label = 'SEALED' }: { label?: string }) {
  return <Badge variant="sealed">{label}</Badge>;
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
            <Badge variant="success">Further review</Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          API promotionStatus = DEVELOPMENT_CANDIDATE_FOR_FURTHER_REVIEW. This is not an approval or
          a claim of profitability — it only means the candidate moves on for further research
          review.
        </TooltipContent>
      </Tooltip>
    );
  }
  if (status === 'NOT_PROMOTED') {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0}>
            <Badge variant="muted">Not promoted</Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>API promotionStatus = NOT_PROMOTED.</TooltipContent>
      </Tooltip>
    );
  }
  return <Badge variant="outline">—</Badge>;
}

import { HelpCircle } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

/**
 * Explains metric units and the decimal → percentage conversion for return
 * metrics. Non-visual fallback: the trigger has an aria-label.
 */
export function UnitHint({
  metricKey,
  children,
}: {
  metricKey: string;
  children: React.ReactNode;
}) {
  const isReturn =
    metricKey === 'weightedSpread' ||
    metricKey.includes('Return') ||
    metricKey.includes('Spread') ||
    metricKey.includes('top5') ||
    metricKey.includes('universe');
  const explanation = isReturn
    ? 'Return metric. The API stores decimals; the UI displays percentages (API 0.0181 → UI 1.81%).'
    : 'Unitless metric (correlation-style). Shown as a plain decimal, not a percentage.';

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex cursor-help items-center gap-1" tabIndex={0} aria-label={explanation}>
          {children}
          <HelpCircle aria-hidden="true" className="h-3.5 w-3.5 text-muted-foreground" />
        </span>
      </TooltipTrigger>
      <TooltipContent>{explanation}</TooltipContent>
    </Tooltip>
  );
}

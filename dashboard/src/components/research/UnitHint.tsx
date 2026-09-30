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
    ? '收益率指标：API 保留小数，界面显示百分比（0.0181 → 1.81%）。'
    : '无量纲相关性指标：显示小数，不转换为百分比。';

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

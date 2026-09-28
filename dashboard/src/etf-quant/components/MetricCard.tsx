import type { ReactNode } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/cn';

/**
 * KPI 指标卡：标签在上、数值居中（tabular-nums）、可选上下文行。
 * tone 仅表达状态语义（success / destructive / info / warning），
 * 涨跌请通过 value 内的带符号数值自行着色，避免两种色相混用。
 */

export type MetricTone = 'default' | 'success' | 'destructive' | 'warning' | 'info' | 'muted';

const TONE_ACCENT: Record<MetricTone, string> = {
  default: 'border-l-transparent',
  success: 'border-l-success',
  destructive: 'border-l-destructive',
  warning: 'border-l-warning',
  info: 'border-l-info',
  muted: 'border-l-border',
};

export function MetricCard({
  label,
  value,
  hint,
  tone = 'default',
  valueClassName,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: MetricTone;
  valueClassName?: string;
  className?: string;
}) {
  return (
    <Card className={cn('border-l-2 py-0', TONE_ACCENT[tone], className)}>
      <CardContent className="flex flex-col gap-1 p-4">
        <p className="text-xs font-medium tracking-wide text-muted-foreground">{label}</p>
        <p className={cn('truncate text-lg font-semibold leading-snug tabular-nums', valueClassName)}>{value}</p>
        {hint ? <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}

export function MetricGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6', className)}>
      {children}
    </div>
  );
}

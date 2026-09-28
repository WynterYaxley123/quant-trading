import type { ReactNode } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/cn';

/** 区块卡片：标题 + 可选说明 + 可选右侧操作。 */
export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-2 space-y-0">
        <div className="flex flex-col gap-1.5">
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </div>
        {actions}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  );
}

/** 分段切换（segmented control）：保持 tablist 语义与键盘可达。 */
export function SegmentedTabs<T extends string>({
  values,
  value,
  onChange,
  label,
}: {
  values: readonly T[];
  value: T;
  onChange: (next: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex w-fit flex-wrap gap-0.5 rounded-lg border border-border bg-muted/50 p-0.5">
      {values.map((v) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={v === value}
          onClick={() => onChange(v)}
          className={cn(
            'rounded-md px-3 py-1 text-sm transition-colors',
            v === value
              ? 'bg-card font-medium text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {v}
        </button>
      ))}
    </div>
  );
}

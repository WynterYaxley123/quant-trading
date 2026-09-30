import type { ReactNode } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/cn';

/**
 * Chart container following the Tremor composition pattern: title +
 * unit-aware description + chart + accessible fallback summary.
 * Charts never mix unit types on a single Y axis.
 */
export function ChartFrame({
  title,
  description,
  summary,
  children,
  className,
  bodyClassName,
}: {
  title: string;
  description?: ReactNode;
  /** Text alternative describing the chart content for screen readers. */
  summary: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <figure role="img" aria-label={summary} className="relative m-0">
          <div className={cn('h-[260px] w-full', bodyClassName)}>{children}</div>
          <figcaption className="sr-only">{summary}</figcaption>
        </figure>
      </CardContent>
    </Card>
  );
}

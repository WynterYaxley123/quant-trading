import * as React from 'react';
import { cn } from '@/lib/cn';

/**
 * Plain semantic table primitives. Wide tables scroll horizontally inside a
 * local container (never page-level overflow).
 */

export function TableContainer({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    // `relative` contains absolutely-positioned sr-only helpers (sort state,
    // caption) so they stay inside this scroll container.
    <div
      className={cn('relative w-full max-w-full overflow-x-auto rounded-lg border border-border', className)}
      {...props}
    />
  );
}

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table className={cn('w-full caption-bottom border-collapse text-sm', className)} {...props} />
  );
}

export function TableHeader({ className, ...props }: React.TableHTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn('bg-muted/60', className)} {...props} />;
}

export function TableBody({ className, ...props }: React.TableHTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn('divide-y divide-border', className)} {...props} />;
}

export function TableRow({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn('transition-colors hover:bg-muted/40', className)}
      {...props}
    />
  );
}

export function TableHead({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        'h-10 whitespace-nowrap px-3 text-left align-middle text-xs font-semibold uppercase tracking-wide text-muted-foreground',
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn('px-3 py-2.5 align-middle', className)} {...props} />;
}

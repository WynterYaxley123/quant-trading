import { useState } from 'react';
import { cn } from '@/lib/cn';
import { abbreviateHash } from '@/lib/hash';

/**
 * Hash display: abbreviated by default (8-12 chars + …), click to reveal the
 * full value. No clipboard/permission APIs — a plain button toggles visibility.
 */
export function HashText({
  value,
  length = 10,
  className,
}: {
  value: string | null | undefined;
  length?: number;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (value === null || value === undefined || value === '') {
    return <span className={cn('font-mono text-xs text-muted-foreground', className)}>—</span>;
  }
  const abbreviated = abbreviateHash(value, length);
  const expandable = value !== abbreviated;

  return (
    <button
      type="button"
      onClick={() => setExpanded((v) => !v)}
      title={expandable ? (expanded ? 'Hide full value' : 'Show full value') : undefined}
      aria-expanded={expandable ? expanded : undefined}
      className={cn(
        'max-w-full break-all rounded px-1 font-mono text-xs text-muted-foreground transition-colors',
        expandable && 'hover:bg-accent hover:text-accent-foreground cursor-pointer',
        !expandable && 'cursor-default',
        className,
      )}
    >
      {expanded ? value : abbreviated}
    </button>
  );
}

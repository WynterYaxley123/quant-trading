import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/cn';

/**
 * Global research status banner — compact but persistent on every research
 * page. It communicates the research phase before any chart is read.
 * Status is conveyed with text (never colour alone).
 */
export function ResearchStatusBanner({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Research status: development only, non-executable, validation sealed, final out-of-sample sealed"
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2',
        className,
      )}
    >
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Research status
      </span>
      <Badge variant="warning">Development only</Badge>
      <Badge variant="destructive">Non-executable</Badge>
      <Badge variant="sealed">Validation sealed</Badge>
      <Badge variant="sealed">Final OOS sealed</Badge>
    </div>
  );
}

import { AlertTriangle, PlugZap, RotateCw, Inbox } from 'lucide-react';
import { Button } from './button';
import { Skeleton } from './skeleton';
import type { ResearchApiError } from '@/api/errors';

/** Loading skeleton with a polite live announcement (accessibility). */
export function LoadingState({ label = 'Loading research data' }: { label?: string }) {
  return (
    <div className="relative flex flex-col gap-3" role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

export function EmptyState({
  title = 'No data available',
  description = 'There is nothing to display for the current selection.',
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border p-10 text-center">
      <Inbox aria-hidden="true" className="h-6 w-6 text-muted-foreground" />
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

/** API disconnected — shown when the Research API cannot be reached. */
export function DisconnectedState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-10 text-center"
      role="alert"
    >
      <PlugZap aria-hidden="true" className="h-6 w-6 text-muted-foreground" />
      <p className="text-base font-semibold">API disconnected</p>
      <p className="max-w-md text-sm text-muted-foreground">
        The read-only Research Data API at the configured base URL is not responding. Research data
        cannot be displayed until the API is running.
      </p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden="true" />
          Retry connection
        </Button>
      ) : null}
    </div>
  );
}

/** Human-readable error state (never a stack trace). */
export function ErrorState({
  error,
  onRetry,
}: {
  error: ResearchApiError;
  onRetry?: () => void;
}) {
  if (error.isDisconnected) return <DisconnectedState onRetry={onRetry} />;
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-destructive/40 p-10 text-center" role="alert">
      <AlertTriangle aria-hidden="true" className="h-6 w-6 text-destructive" />
      <p className="text-base font-semibold">Could not load research data</p>
      <p className="max-w-md text-sm text-muted-foreground">{error.userMessage}</p>
      <p className="text-xs text-muted-foreground">Error code: {error.code}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden="true" />
          Retry
        </Button>
      ) : null}
    </div>
  );
}

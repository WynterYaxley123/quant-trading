import { useCallback, useEffect, useMemo, useState } from 'react';
import { isResearchApiError, ResearchApiError } from '@/api/errors';

/**
 * Small async-resource hook (a full server-state library is deliberately not
 * introduced): loading / error / data with AbortController cancellation and a
 * retry(). Errors surface as typed ResearchApiError so pages can render
 * "API disconnected" vs. human-readable API errors — never stack traces.
 *
 * Loading state is derived by comparing the settled result key with the
 * current request key, so no synchronous setState happens inside effects.
 */

export interface ResourceState<T> {
  data: T | null;
  loading: boolean;
  error: ResearchApiError | null;
  retry: () => void;
}

interface SettledResult<T> {
  key: string;
  data: T | null;
  error: ResearchApiError | null;
}

export function useResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): ResourceState<T> {
  const [attempt, setAttempt] = useState(0);
  const key = useMemo(() => `${JSON.stringify(deps)}#${attempt}`, [deps, attempt]);
  const [settled, setSettled] = useState<SettledResult<T>>({
    key: '',
    data: null,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    // `fetcher` intentionally rides the closure of the render that changed
    // the request key; `deps` must list every input it captures.
    void fetcher(controller.signal)
      .then((data) => {
        if (!cancelled) setSettled({ key, data, error: null });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setSettled({
          key,
          data: null,
          error: isResearchApiError(cause)
            ? cause
            : new ResearchApiError('UNKNOWN', cause instanceof Error ? cause.message : undefined),
        });
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const pending = settled.key !== key;
  return {
    data: pending ? null : settled.data,
    loading: pending,
    error: pending ? null : settled.error,
    retry,
  };
}

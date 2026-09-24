import type { z } from 'zod';
import { apiErrorEnvelopeSchema, SCHEMA_VERSION } from './contracts';
import { createApiError, ResearchApiError } from './errors';

/**
 * Minimal typed HTTP client for the READ-ONLY Research Data API v1.
 *
 * - base URL comes from configuration, never from components
 * - request timeout with AbortController (also honours caller aborts)
 * - query-string encoding for arrays/booleans/numbers
 * - unwraps the `{ schemaVersion, data }` / `{ schemaVersion, error }` envelope
 * - runtime-validates `data` with the caller-provided zod schema
 */

export interface ClientOptions {
  baseUrl: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export interface QueryValue {
  [key: string]: string | number | boolean | undefined | null;
}

const DEFAULT_TIMEOUT_MS = 10_000;

export function encodeQuery(query: QueryValue | undefined): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

/** Link a caller-provided signal to our own timeout signal. */
function linkSignals(
  callerSignal: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new DOMException('timeout', 'TimeoutError')), timeoutMs);
  const onCallerAbort = () => controller.abort(callerSignal?.reason);
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort(callerSignal.reason);
    else callerSignal.addEventListener('abort', onCallerAbort);
  }
  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timer);
      callerSignal?.removeEventListener('abort', onCallerAbort);
    },
  };
}

export class ResearchApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  async get<T>(
    path: string,
    schema: z.ZodType<T>,
    query?: QueryValue,
    signal?: AbortSignal,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}${encodeQuery(query)}`;
    const { signal: linkedSignal, cleanup } = linkSignals(signal, this.timeoutMs);

    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: linkedSignal,
      });
    } catch (cause) {
      cleanup();
      if (isAbortFromTimeout(cause, linkedSignal)) {
        throw new ResearchApiError('TIMEOUT');
      }
      if (signal?.aborted) {
        // Caller cancelled (e.g. navigating away) — not an API failure.
        throw new ResearchApiError('UNKNOWN', 'Request cancelled');
      }
      throw new ResearchApiError('NETWORK_UNREACHABLE');
    }
    cleanup();

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new ResearchApiError('INVALID_RESPONSE', 'Response body was not JSON', response.status);
    }

    const envelope = apiErrorEnvelopeSchema.safeParse(body);
    if (response.status >= 400 || (envelope.success && 'error' in (body as object))) {
      const code = envelope.success ? envelope.data.error.code : 'UNKNOWN';
      const message = envelope.success ? envelope.data.error.message : undefined;
      throw createApiError(code, message, response.status);
    }

    const wrapped = body as { schemaVersion?: string; data?: unknown };
    if (wrapped.schemaVersion !== SCHEMA_VERSION || !('data' in wrapped)) {
      throw new ResearchApiError(
        'INVALID_RESPONSE',
        `Expected schemaVersion ${SCHEMA_VERSION} success envelope`,
        response.status,
      );
    }

    const parsed = schema.safeParse(wrapped.data);
    if (!parsed.success) {
      throw new ResearchApiError(
        'INVALID_RESPONSE',
        'Response data did not match the API v1 contract shape',
        response.status,
      );
    }
    return parsed.data;
  }
}

function isAbortFromTimeout(cause: unknown, linkedSignal: AbortSignal): boolean {
  if (!linkedSignal.aborted) return false;
  const reason = (linkedSignal.reason ?? cause) as { name?: string } | undefined;
  return reason?.name === 'TimeoutError';
}

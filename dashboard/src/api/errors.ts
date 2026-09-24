/**
 * Typed API errors.
 *
 * Server-reported codes come from the frozen API v1 contract; client-side
 * codes cover transport and parsing failures. UI must never show stack
 * traces — only `userMessage`.
 */

export const SERVER_ERROR_CODES = [
  'BAD_QUERY',
  'RUN_NOT_FOUND',
  'CANDIDATE_NOT_FOUND',
  'SEALED_PHASE',
  'ARTIFACT_SCHEMA_ERROR',
  'ARTIFACT_IO_ERROR',
  'PATH_TRAVERSAL_BLOCKED',
  'METHOD_NOT_ALLOWED',
] as const;
export type ServerErrorCode = (typeof SERVER_ERROR_CODES)[number];

export const CLIENT_ERROR_CODES = [
  'NETWORK_UNREACHABLE',
  'TIMEOUT',
  'INVALID_RESPONSE',
  'UNKNOWN',
] as const;
export type ClientErrorCode = (typeof CLIENT_ERROR_CODES)[number];

export type ApiErrorCode = ServerErrorCode | ClientErrorCode | (string & {});

const USER_MESSAGES: Record<string, string> = {
  BAD_QUERY:
    'The request parameters were not valid. Adjust the selected run / candidate / date and try again.',
  RUN_NOT_FOUND: 'The requested research run does not exist.',
  CANDIDATE_NOT_FOUND: 'The requested candidate does not exist in this run.',
  SEALED_PHASE:
    'This data belongs to a sealed phase (Validation / Final OOS) and is not accessible in development.',
  ARTIFACT_SCHEMA_ERROR:
    'A research artifact did not match the expected schema. The research artifacts may be incomplete.',
  ARTIFACT_IO_ERROR:
    'A research artifact could not be read. Check that the Research API process is running.',
  PATH_TRAVERSAL_BLOCKED: 'The request was rejected by the API safety checks.',
  METHOD_NOT_ALLOWED: 'That operation is not allowed on the read-only Research API.',
  NETWORK_UNREACHABLE: 'API disconnected',
  TIMEOUT: 'The Research API did not respond in time.',
  INVALID_RESPONSE:
    'The Research API returned a response that did not match the API v1 contract.',
  UNKNOWN: 'An unexpected error occurred while loading research data.',
};

export class ResearchApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number | null;

  constructor(code: ApiErrorCode, message?: string, status: number | null = null) {
    super(message ?? USER_MESSAGES[code] ?? USER_MESSAGES.UNKNOWN ?? 'Unknown error');
    this.name = 'ResearchApiError';
    this.code = code;
    this.status = status;
  }

  /** Human-readable text safe to render in the UI (never a stack trace). */
  get userMessage(): string {
    return USER_MESSAGES[this.code] ?? USER_MESSAGES.UNKNOWN ?? 'An unexpected error occurred.';
  }

  /** True when the API cannot be reached at all (show "API disconnected"). */
  get isDisconnected(): boolean {
    return this.code === 'NETWORK_UNREACHABLE' || this.code === 'TIMEOUT';
  }
}

/** Map a raw string code from the wire into a typed error. */
export function createApiError(
  code: string,
  message: string | undefined,
  status: number | null = null,
): ResearchApiError {
  const known = (SERVER_ERROR_CODES as readonly string[]).includes(code)
    ? (code as ServerErrorCode)
    : (code as ApiErrorCode);
  return new ResearchApiError(known, message, status);
}

export function isResearchApiError(error: unknown): error is ResearchApiError {
  return error instanceof ResearchApiError;
}

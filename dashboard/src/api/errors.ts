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
  'RESEARCH_APPROVAL_INVALID', 'RESEARCH_APPROVAL_AMBIGUOUS', 'RESEARCH_CONFIGURATION_INVALID',
  'RESEARCH_ARTIFACT_INVALID', 'RESEARCH_ARTIFACT_UNAPPROVED',
  'RESEARCH_ARTIFACT_HASH_MISMATCH', 'RESEARCH_ARTIFACT_PHASE_FORBIDDEN',
  'HOST_NOT_ALLOWED', 'ORIGIN_NOT_ALLOWED',
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
  BAD_QUERY: '查询参数无效，请检查运行记录、候选方案和日期。',
  RUN_NOT_FOUND: '未找到研究运行记录。',
  CANDIDATE_NOT_FOUND: '未找到候选方案。',
  SEALED_PHASE: '该研究阶段仍处于封存状态，不可访问。',
  ARTIFACT_SCHEMA_ERROR: '研究产物结构校验失败。',
  ARTIFACT_IO_ERROR: '无法读取研究产物。',
  PATH_TRAVERSAL_BLOCKED: '非法路径访问已被阻止。',
  METHOD_NOT_ALLOWED: '当前接口仅允许只读访问。',
  RESEARCH_ARTIFACT_HASH_MISMATCH: '研究产物 Hash 与获准清单不一致，请恢复完整产物后重新校验。',
  RESEARCH_ARTIFACT_UNAPPROVED: '所选研究产物未获准访问。',
  RESEARCH_ARTIFACT_PHASE_FORBIDDEN: '所选产物不是获准的 Development 阶段。',
  RESEARCH_ARTIFACT_INVALID: '已配置的研究产物缺失或无效。',
  RESEARCH_APPROVAL_INVALID: '研究产物批准清单无效。',
  RESEARCH_APPROVAL_AMBIGUOUS: '请在本机配置中指定获准的工作区身份。',
  RESEARCH_CONFIGURATION_INVALID: '本机研究工作区配置无效。',
  HOST_NOT_ALLOWED: '研究接口仅允许本机访问。',
  ORIGIN_NOT_ALLOWED: '请求来源未获准。',
  NETWORK_UNREACHABLE: '研究数据接口未连接。',
  TIMEOUT: '研究数据接口响应超时。',
  INVALID_RESPONSE: '研究数据接口返回内容与 V1 契约不符。',
  UNKNOWN: '加载研究数据时发生未知错误。',
};

export class ResearchApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number | null;

  constructor(code: ApiErrorCode, message?: string, status: number | null = null) {
    super(message ?? USER_MESSAGES[code] ?? USER_MESSAGES.UNKNOWN ?? '未知错误');
    this.name = 'ResearchApiError';
    this.code = code;
    this.status = status;
  }

  /** Human-readable text safe to render in the UI (never a stack trace). */
  get userMessage(): string {
    return USER_MESSAGES[this.code] ?? USER_MESSAGES.UNKNOWN ?? '发生未知错误。';
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

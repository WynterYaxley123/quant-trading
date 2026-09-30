export type ApiErrorCode =
  | 'BAD_QUERY' | 'RUN_NOT_FOUND' | 'CANDIDATE_NOT_FOUND' | 'SEALED_PHASE'
  | 'ARTIFACT_SCHEMA_ERROR' | 'ARTIFACT_IO_ERROR' | 'PATH_TRAVERSAL_BLOCKED'
  | 'METHOD_NOT_ALLOWED'
  | 'ROUTE_NOT_FOUND'

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    public readonly status: 400 | 403 | 404 | 405 | 500,
    message: string,
    public readonly context?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function schemaError(context: string, detail: string): never {
  throw new ApiError('ARTIFACT_SCHEMA_ERROR', 500, 'Research artifact schema is invalid', `${context}: ${detail}`)
}

import { createHash } from 'node:crypto'
import { readFile, readdir, realpath } from 'node:fs/promises'
import { isAbsolute, relative, resolve, sep } from 'node:path'
import { ApiError, schemaError } from '../errors.js'

export function assertSafeSegment(segment: string): void {
  if (!segment || segment === '.' || segment.includes('..') || /[/\\:%\0]/.test(segment)
      || isAbsolute(segment)) {
    throw new ApiError('PATH_TRAVERSAL_BLOCKED', 403, 'Path traversal blocked')
  }
  // Reject all encoded path spellings rather than decoding twice and accepting aliases.
  if (/%/i.test(segment)) throw new ApiError('PATH_TRAVERSAL_BLOCKED', 403, 'Path traversal blocked')
}

function contained(root: string, target: string): boolean {
  const rel = relative(root, target)
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel))
}

export class ArtifactStorage {
  constructor(private readonly configuredRoot: string) {}

  private async root(): Promise<string> {
    try {
      return await realpath(resolve(this.configuredRoot))
    } catch (error) {
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact root is unavailable',
        `report root: ${String(error)}`)
    }
  }

  private async inside(segments: readonly string[], missingCode: 'RUN_NOT_FOUND' | 'ARTIFACT_IO_ERROR'):
    Promise<string> {
    segments.forEach(assertSafeSegment)
    const root = await this.root()
    const lexical = resolve(root, ...segments)
    if (!contained(root, lexical)) {
      throw new ApiError('PATH_TRAVERSAL_BLOCKED', 403, 'Path traversal blocked')
    }
    let actual: string
    try {
      actual = await realpath(lexical)
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT' && missingCode === 'RUN_NOT_FOUND') {
        throw new ApiError('RUN_NOT_FOUND', 404, 'Research run not found')
      }
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact unavailable',
        `${segments.join('/')}: ${String(error)}`)
    }
    if (!contained(root, actual)) {
      throw new ApiError('PATH_TRAVERSAL_BLOCKED', 403, 'Path traversal blocked')
    }
    return actual
  }

  async read(segments: readonly string[], expectedSha: string | null = null,
             missingCode: 'RUN_NOT_FOUND' | 'ARTIFACT_IO_ERROR' = 'ARTIFACT_IO_ERROR'):
    Promise<string> {
    const path = await this.inside(segments, missingCode)
    let bytes: Buffer
    try {
      bytes = await readFile(path)
    } catch (error) {
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact unavailable',
        `${segments.join('/')}: ${String(error)}`)
    }
    if (expectedSha !== null && createHash('sha256').update(bytes).digest('hex') !== expectedSha) {
      schemaError(segments.join('/'), 'SHA256 does not match official metadata manifest')
    }
    return bytes.toString('utf8')
  }

  async directories(segments: readonly string[]): Promise<string[]> {
    const path = await this.inside(segments, 'ARTIFACT_IO_ERROR')
    try {
      const entries = await readdir(path, { withFileTypes: true })
      return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort()
    } catch (error) {
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact catalog unavailable',
        `${segments.join('/')}: ${String(error)}`)
    }
  }
}

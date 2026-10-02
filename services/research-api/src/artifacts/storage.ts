import { createHash } from 'node:crypto'
import { readFile, readdir, realpath } from 'node:fs/promises'
import { isAbsolute, relative, resolve, sep } from 'node:path'
import { ApiError } from '../errors.js'

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

  async root(): Promise<string> {
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

  async readHashed(segments: readonly string[], expectedSha: string | null = null,
             missingCode: 'RUN_NOT_FOUND' | 'ARTIFACT_IO_ERROR' = 'ARTIFACT_IO_ERROR'):
    Promise<{ text: string; sha256: string }> {
    const path = await this.inside(segments, missingCode)
    let bytes: Buffer
    try {
      bytes = await readFile(path)
    } catch (error) {
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact unavailable',
        `${segments.join('/')}: ${String(error)}`)
    }
    const sha256 = createHash('sha256').update(bytes).digest('hex')
    if (expectedSha !== null && sha256 !== expectedSha) {
      throw new ApiError('RESEARCH_ARTIFACT_HASH_MISMATCH', 500, 'Artifact SHA256 does not match its approved manifest', segments.join('/'))
    }
    return { text: bytes.toString('utf8'), sha256 }
  }

  async read(segments: readonly string[], expectedSha: string | null = null,
             missingCode: 'RUN_NOT_FOUND' | 'ARTIFACT_IO_ERROR' = 'ARTIFACT_IO_ERROR') {
    return (await this.readHashed(segments, expectedSha, missingCode)).text
  }

  async directories(segments: readonly string[]): Promise<string[]> {
    segments.forEach(assertSafeSegment)
    // A deployment without optional reports is a valid empty catalog. Only
    // absence is optional: permissions, broken manifests and escapes still fail.
    try {
      await realpath(resolve(this.configuredRoot))
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact root is unavailable')
    }
    let path: string
    try {
      path = await this.inside(segments, 'RUN_NOT_FOUND')
    } catch (error) {
      if (error instanceof ApiError && error.code === 'RUN_NOT_FOUND') return []
      throw error
    }
    try {
      const entries = await readdir(path, { withFileTypes: true })
      return entries.filter((entry) => entry.isDirectory() || entry.isSymbolicLink()).map((entry) => entry.name).sort()
    } catch (error) {
      throw new ApiError('ARTIFACT_IO_ERROR', 500, 'Research artifact catalog unavailable',
        `${segments.join('/')}: ${String(error)}`)
    }
  }
}

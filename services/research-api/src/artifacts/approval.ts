import { readFile } from 'node:fs/promises'
import { z } from 'zod'
import { ApiError } from '../errors.js'

const runApproval = z.object({
  runId: z.string().regex(/^iteration1_\d{8}_\d{6}_\d{6}_utc$/),
  createdAt: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/)
    .refine((value) => Number.isFinite(Date.parse(value)), 'Invalid UTC creation time'),
  timeSource: z.literal('METADATA_RUN_ID_UTC'),
  metadataSha256: z.string().regex(/^[a-f0-9]{64}$/),
}).strict().refine((run) => {
  const m = run.runId.match(/^iteration1_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(\d{6})_utc$/)!
  return run.createdAt === `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}.${m[7]}Z`
}, 'Creation time differs from metadata run identity')

const workspaceApproval = z.object({
  artifactId: z.string().regex(/^[a-z0-9][a-z0-9-]*$/),
  collection: z.literal('shenwan_sector_index'),
  phase: z.literal('DEVELOPMENT'),
  approvalState: z.literal('APPROVED'),
  approvalBasis: z.literal('OWNER_AUTHORIZED_EXISTING_DEVELOPMENT_ACCEPTANCE'),
  evidence: z.string().min(1),
  runs: z.array(runApproval).min(1),
}).strict().refine((workspace) => new Set(workspace.runs.map((run) => run.runId)).size === workspace.runs.length,
  'Duplicate approved run identity')

export const registrySchema = z.object({
  schemaVersion: z.literal('1.0.0'), workspaces: z.array(workspaceApproval),
}).strict().refine((registry) => new Set(registry.workspaces.map((item) => item.artifactId)).size === registry.workspaces.length,
  'Duplicate workspace identity')
export type WorkspaceApproval = z.infer<typeof workspaceApproval>

export async function readApproval(path: string, artifactId?: string): Promise<WorkspaceApproval | null> {
  let raw: unknown
  try { raw = JSON.parse((await readFile(path, 'utf8')).replace(/^\uFEFF/, '')) }
  catch { throw new ApiError('RESEARCH_APPROVAL_INVALID', 500, 'Approval registry is unavailable or malformed') }
  const parsed = registrySchema.safeParse(raw)
  if (!parsed.success) throw new ApiError('RESEARCH_APPROVAL_INVALID', 500, 'Approval registry failed validation')
  const workspaces = parsed.data.workspaces
  if (artifactId) {
    const selected = workspaces.find((item) => item.artifactId === artifactId)
    if (!selected) throw new ApiError('RESEARCH_ARTIFACT_UNAPPROVED', 403, 'Configured workspace identity is not approved')
    return selected
  }
  if (workspaces.length > 1) throw new ApiError('RESEARCH_APPROVAL_AMBIGUOUS', 500, 'Select an approved workspace identity in local configuration')
  return workspaces[0] ?? null
}

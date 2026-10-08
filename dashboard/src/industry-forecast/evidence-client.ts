import { z } from 'zod';
import { industryForecastBaseUrl } from '@/lib/env';

export const evidenceReadinessSchema=z.object({
  schema_version:z.literal(1),scope:z.literal('TESTED_INFRASTRUCTURE_NOT_LIVE_ACTIVATION'),
  models:z.object({swl1_ridge_v1:z.literal('FAILED_VALIDATION'),swl1_ridge_v2:z.literal('FAILED_VALIDATION')}).strict(),
  source_admission_status:z.literal('BLOCKED_UNVERIFIED_RIGHTS'),PIT_confidence:z.literal('RECONSTRUCTED_TIER_C'),
  historical_numeric_access_isolation:z.literal('NOT_CERTIFIED'),certified_historically_unseen_sessions:z.literal(0),
  infrastructure_readiness:z.literal('TESTED_SYNTHETIC_ONLY'),logical_boundary:z.literal('PASS_SYNTHETIC'),physical_view_boundary:z.literal('PASS_SYNTHETIC'),
  process_isolation:z.literal('PASS_LINUX_DOCKER_SYNTHETIC'),windows_native_process_isolation:z.literal('NOT_ESTABLISHED'),
  signature_authority:z.literal('SIGNATURE_AUTHORITY_NOT_ESTABLISHED'),future_protocol:z.literal('NOT_CREATED'),
  formal_prospective_evidence:z.literal('NONE'),formal_observations:z.literal(0),real_forecasts:z.literal(0),live_activation:z.literal(false),
  next_generation_research_readiness:z.literal('DATA_SOURCE_NOT_READY'),
  maturity:z.array(z.object({horizon:z.union([z.literal(10),z.literal(40),z.literal(120)]),status:z.literal('PENDING_MATURITY'),matured_observations:z.literal(0)}).strict()).length(3),
  decision:z.literal('C'),blocking_gaps:z.array(z.string().max(100)).max(10),recommended_data_gap_remediation:z.array(z.string().max(500)).max(10),
}).strict();
export async function fetchEvidenceReadiness(signal:AbortSignal) {
  const response=await fetch(`${industryForecastBaseUrl()}/research-evidence/prospective-status`,{signal});
  if(!response.ok)throw new Error('Evidence readiness unavailable');
  const envelope=z.object({schemaVersion:z.literal('1.0.0'),data:evidenceReadinessSchema,error:z.null()}).strict().parse(await response.json());
  return envelope.data;
}

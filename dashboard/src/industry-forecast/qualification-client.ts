import { z } from 'zod';
import { industryForecastBaseUrl } from '@/lib/env';

const text=z.string().min(1).max(600);
export const sourceQualificationSchema=z.object({
  schema_version:z.literal(1),scope:z.literal('PUBLIC_METADATA_ONLY_NO_REAL_SOURCE_PROMOTION'),
  source_identity:text,evidence_reference:z.literal('config/research/swl1-source-qualification-evidence.json'),
  retrieval_timestamp:z.string().datetime({offset:true}),document_hash:z.string().regex(/^[a-f0-9]{64}$/),
  admission_requirement:text,verification_result:z.literal('REAL_ADMISSION_BLOCKED'),remaining_gap:text,
  current_sources_audited:z.number().int().min(1).max(50),official_documents_verified:z.number().int().min(0).max(50),
  public_documents_collected:z.number().int().min(0).max(50),attempted_document_endpoints:z.number().int().min(0).max(50),
  real_source_rights_verified:z.literal(0),real_pit_sources_verified:z.literal(0),real_sources_admitted:z.literal(0),
  rights_readiness:z.literal('BLOCKED_DATASET_SPECIFIC_GRANTS_NOT_ESTABLISHED'),pit_readiness:z.literal('CONTEMPORANEOUS_MEMBERSHIP_NOT_ESTABLISHED'),
  quality_readiness:z.literal('METADATA_REVIEWED_NUMERIC_QA_BLOCKED'),official_index_source:z.literal('NOT_ESTABLISHED'),
  production_authority:z.literal('SIGNATURE_AUTHORITY_NOT_ESTABLISHED'),linux_worker_isolation:z.literal('PASS_LINUX_DOCKER_SYNTHETIC'),
  windows_native_isolation:z.literal('NOT_ESTABLISHED'),independent_unseen_evidence_ready:z.literal(false),research_readiness:z.literal('DATA_SOURCE_NOT_READY'),next_decision:z.literal('C'),
  formal_observations:z.literal(0),formal_forecasts:z.literal(0),future_protocol:z.literal('NOT_CREATED'),historical_access_isolation:z.literal('NOT_CERTIFIED'),certified_historically_unseen_sessions:z.literal(0),
  models:z.object({swl1_v1:z.literal('FAILED_VALIDATION'),swl1_v2:z.literal('FAILED_VALIDATION')}).strict(),
  sources:z.array(z.object({source_id:z.string().regex(/^[a-z0-9-]{1,96}$/),provider:text,dataset:text,kind:text,source_admission:z.literal('SOURCE_BLOCKED')}).strict()).max(50),
  owner_actions:z.array(z.object({id:z.string().regex(/^OWNER_[A-Z]+$/),provider:text,action:text,packet:z.string().regex(/^docs\/(?:research\/source-qualification\/vendor-evidence-requests\/[a-z]+|engineering\/[a-z-]+)\.md$/)}).strict()).max(10),
  production_identity_requirements:z.array(text).max(10),no_credentials_inspected:z.literal(true),no_production_keys_created:z.literal(true),
  external_provider_confirmations_required:z.number().int().min(0).max(10),license_requests_required:z.number().int().min(0).max(10),owner_approval_actions:z.number().int().min(0).max(10),
  performance_blind:z.literal(true),numeric_qa_run:z.literal(false),
}).strict().refine(q=>q.current_sources_audited===q.sources.length && new Set(q.sources.map(s=>s.source_id)).size===q.sources.length && q.owner_approval_actions===q.owner_actions.length && q.official_documents_verified<=q.public_documents_collected && q.public_documents_collected<=q.attempted_document_endpoints,'Qualification counts do not match reviewed records');

export async function fetchSourceQualification(signal:AbortSignal) {
  const response=await fetch(`${industryForecastBaseUrl()}/research-evidence/source-qualification`,{signal});
  if(!response.ok)throw new Error('Source qualification unavailable');
  return z.object({schemaVersion:z.literal('1.0.0'),data:sourceQualificationSchema,error:z.null()}).strict().parse(await response.json()).data;
}

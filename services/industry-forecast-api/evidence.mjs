/** Aggregate public metadata only; no runtime, provider or numeric-materialization API. */
import {createHash} from 'node:crypto';
import {boundedLeaf} from '../etf-quant-api/bounded.mjs';
import {verifyCurrentCertificate,certificateHash} from '../etf-quant-runner/security-audit.mjs';

const ACTIVE='reports/engineering/swl1-rev10-delivery-integrity.json';
const PARENT='reports/engineering/shadow-task-installation-integrity.json';
const DIR='reports/research/swl1_data_first/';
const check=v=>{if(!v)throw new Error('RESEARCH_EVIDENCE_INTEGRITY_BLOCKER');};
const sha=raw=>createHash('sha256').update(raw).digest('hex');
export async function verifiedResearchFiles(root) {
  const read=async(name,limit=2*1024*1024)=>(await boundedLeaf(root,name,limit)).raw;
  const [currentRaw,parentRaw]=await Promise.all([read(ACTIVE),read(PARENT)]);
  const parent=JSON.parse(parentRaw).implementation_integrity;check(parent.certificate_sha256===certificateHash(parent));
  const integrity=verifyCurrentCertificate(JSON.parse(currentRaw).implementation_integrity,parent,parentRaw,PARENT);
  const entries=Object.entries(integrity.files);
  for(let i=0;i<entries.length;i+=8)await Promise.all(entries.slice(i,i+8).map(async([name,hash])=>check(sha(await read(name))===hash)));
  return integrity.files;
}
export async function publicEvidence(root,resource) {
  const read=async(name,limit=2*1024*1024)=>(await boundedLeaf(root,name,limit)).raw;
  const files=await verifiedResearchFiles(root);
  const reports={};
  for(const name of ['source-inventory','source-admission-summary','pit-evidence-assessment','prospective-readiness']) {
    const p=`${DIR}${name}.json`,raw=await read(p,64*1024);check(files[p]===sha(raw));reports[name]=JSON.parse(raw);
  }
  const r=reports['prospective-readiness'];
  check(r.formal_observations===0 && r.real_forecasts===0 && r.live_activation===false && r.future_protocol==='NOT_CREATED' && r.models.swl1_ridge_v1==='FAILED_VALIDATION' && r.models.swl1_ridge_v2==='FAILED_VALIDATION' && r.historical_numeric_access_isolation==='NOT_CERTIFIED');
  if(resource==='source-qualification') {
    const p='reports/research/swl1_source_qualification/final-readiness.json',raw=await read(p,64*1024);check(files[p]===sha(raw));
    const q=JSON.parse(raw);
    check(q.scope==='PUBLIC_METADATA_ONLY_NO_REAL_SOURCE_PROMOTION' && q.real_sources_admitted===0 && q.real_source_rights_verified===0 && q.real_pit_sources_verified===0 && q.research_readiness==='DATA_SOURCE_NOT_READY' && q.production_authority==='SIGNATURE_AUTHORITY_NOT_ESTABLISHED' && q.formal_observations===0 && q.formal_forecasts===0 && q.future_protocol==='NOT_CREATED' && q.historical_access_isolation==='NOT_CERTIFIED' && q.certified_historically_unseen_sessions===0 && q.numeric_qa_run===false && q.performance_blind===true && q.no_production_keys_created===true && q.independent_unseen_evidence_ready===false && q.models.swl1_v1==='FAILED_VALIDATION' && q.models.swl1_v2==='FAILED_VALIDATION');
    check(Array.isArray(q.sources) && q.sources.length===q.current_sources_audited && new Set(q.sources.map(s=>s.source_id)).size===q.sources.length && q.sources.every(s=>s.source_admission==='SOURCE_BLOCKED'));
    return q;
  }
  if(resource==='sources')return reports['source-inventory'];
  if(resource==='source-admissions')return reports['source-admission-summary'];
  if(resource==='prospective-status')return r;
  if(resource==='maturity-status')return {schema_version:1,formal_observations:0,lifecycle:'NOT_PREREGISTERED',maturity:r.maturity,overlap_independence:'NOT_APPLICABLE_NO_REAL_OBSERVATIONS'};
  if(resource==='access-policy')return {schema_version:1,default:'DATA_ACCESS_DENIED',scope:r.scope,logical_boundary:r.logical_boundary,physical_view_boundary:r.physical_view_boundary,process_isolation:r.process_isolation,windows_native_process_isolation:r.windows_native_process_isolation,signature_authority:r.signature_authority,worker_mounts:['/view:readonly','/policy:readonly'],network:'none',production_activation:'BLOCKED',feature_return_cutoffs:'SEPARATE',raw_numeric_response:false};
  throw new Error('INVALID_RESOURCE');
}

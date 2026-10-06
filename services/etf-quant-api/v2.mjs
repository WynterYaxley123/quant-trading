/** Bounded, read-only V2 aggregates. No market rows, fit or runtime creation. */
import {realpath} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {repositoryFile,verifyCurrentCertificate} from '../etf-quant-runner/security-audit.mjs';
import {boundedLeaf} from './bounded.mjs';

const defaultRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const CANDIDATE='strategies/etf_quant_v2/config/candidate.json';
const REPORT='reports/engineering/etf-quant-v2-build-research.json';
export const CURRENT_MANIFEST='reports/engineering/v8-integrity.json';
const MANIFEST=CURRENT_MANIFEST;
const PARENTS=['reports/engineering/shadow-task-installation-integrity.json','reports/engineering/shadow-operations-integrity.json','reports/engineering/forward-shadow-closure-integrity.json','reports/engineering/etf-quant-v2-console-integrity.json','reports/engineering/etf-quant-v2-factual-units-integrity.json','reports/engineering/etf-quant-v2-factual-refresh-integrity.json','reports/engineering/etf-quant-v2-observation-integrity.json',
  'reports/engineering/etf-quant-v2-finalization-integrity.json','reports/engineering/etf-quant-v2-build-integrity.json'];
const FINAL='reports/engineering/etf-quant-v2-final-oos.json';
const RELEASE='strategies/etf_quant_v2/config/release.json';
const MAPPING='reports/engineering/etf-quant-v2-mapping-study.json';
const REGISTRY='strategies/etf_quant_v2/config/mapping-registry.json';
const ASSESSMENT='config/research/etf-quant-v2-scientific-status.json';
const LABELS=['scientific_status','product_status','final_oos_directional_label','independent_statistical_confidence',
  'historical_membership_confidence','etf_execution_historical_validation'];
const sha=b=>createHash('sha256').update(b).digest('hex');
const requireValue=v=>{if(!v)throw new Error('V2_RESEARCH_INTEGRITY_BLOCKER');};

async function bounded(root,name) {
  repositoryFile(root,name);
  return (await boundedLeaf(root,name,512*1024)).raw;
}
export async function observeV2(root=defaultRoot) {
  const real=await realpath(root);
  const [candidateBytes,reportBytes,manifestBytes,...parentBytes]=await Promise.all([CANDIDATE,REPORT,MANIFEST,...PARENTS].map(n=>bounded(real,n)));
  const candidate=JSON.parse(candidateBytes),report=JSON.parse(reportBytes);
  let manifest=JSON.parse(manifestBytes).implementation_integrity;
  let child=manifest;
  for(let i=0;i<PARENTS.length;i++) {
    const parent=JSON.parse(parentBytes[i]).implementation_integrity;
    const verified=verifyCurrentCertificate(child,parent,parentBytes[i],PARENTS[i]);
    if(i===0)manifest=verified;
    child=parent;
  }
  // Verify every certified source, not merely report self-consistency.
  // Bound parallel I/O to eight descriptors while retaining every full-file hash.
  const entries=Object.entries(manifest.files);
  for(let start=0;start<entries.length;start+=8)await Promise.all(entries.slice(start,start+8).map(async([name,expected])=>requireValue(sha(await bounded(real,name))===expected)));
  // Python's frozen identity preserves 30.0; JS JSON normalizes it to 30.
  // The transition binds exact candidate/report bytes instead of reserializing.
  requireValue(candidate.product==='ETF_QUANT_V2' && /^[a-f0-9]{64}$/.test(candidate.candidate_sha256)
    && manifest.files[CANDIDATE]===sha(candidateBytes) && manifest.files[REPORT]===sha(reportBytes)
    && report.candidate_sha256===candidate.candidate_sha256 && candidate.validation_open_count===1
    && candidate.final_oos_opened===false && candidate.shadow_started===false && candidate.broker_enabled===false && candidate.real_order_path===false);
  const [finalBytes,releaseBytes,mappingBytes,registryBytes]=await Promise.all([FINAL,RELEASE,MAPPING,REGISTRY].map(n=>bounded(real,n)));
  for(const [name,bytes] of [[FINAL,finalBytes],[RELEASE,releaseBytes],[MAPPING,mappingBytes],[REGISTRY,registryBytes]])requireValue(manifest.files[name]===sha(bytes));
  const final=JSON.parse(finalBytes),originalRelease=JSON.parse(releaseBytes),mapping=JSON.parse(mappingBytes),registry=JSON.parse(registryBytes);
  const {classification:historicalClassification,...release}=originalRelease;
  const statuses={PASS_STRONG:'HISTORICALLY_VALIDATED_STRONG',PASS_WEAK:'HISTORICALLY_VALIDATED_WEAK',FAIL:'FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT'};
  requireValue(final.candidate_sha256===candidate.candidate_sha256 && final.open_count===1 && final.model_retuned===false
    && final.decision.scientific_status===statuses[final.decision.classification] && release.scientific_status===final.decision.scientific_status
    && release.final_oos_sha256===sha(finalBytes) && release.registry_sha256===registry.registry_sha256 && release.candidate_sha256===candidate.candidate_sha256
    && release.broker_enabled===false && release.real_order_path===false && registry.proxy_threshold===40 && registry.frozen===true);
  const assessmentBytes=await bounded(real,ASSESSMENT),assessment=JSON.parse(assessmentBytes);
  requireValue(manifest.files[ASSESSMENT]===sha(assessmentBytes)
    && assessment.candidate_sha256===candidate.candidate_sha256 && assessment.final_oos_sha256===sha(finalBytes)
    && assessment.original_final_oos_sessions===final.metrics.signals && assessment.original_final_oos_consumed===true
    && assessment.original_final_oos_resealed===false && assessment.post_oos_extension===null);
  requireValue(Object.keys(assessment.labels).length===LABELS.length && LABELS.every(k=>Object.hasOwn(assessment.labels,k)));
  // Current labels come only from the certified overlay; immutable gate outputs keep explicitly historical names.
  Object.assign(release,{historical_classification:historicalClassification},assessment.labels);
  const {scientific_status:historicalScientific,product_status:historicalProduct,...decision}=final.decision;
  const finalView={...final,decision:{...decision,historical_scientific_status:historicalScientific,historical_product_status:historicalProduct}};
  return {product:'ETF_QUANT_V2',research_status:release.scientific_status,candidate_sha256:candidate.candidate_sha256,
    specification:candidate.specification,evidence_mode:candidate.evidence_mode,historical_start:report.historical.start,
    historical_end:report.historical.end,trading_sessions:report.historical.trading_sessions,history_years:report.historical.history_years,
    membership_tier_rows:report.historical.membership_tier_rows,development:report.revision.selected.metrics,
    validation_status:report.validation.status,validation:report.validation.results.find(r=>r.mode===candidate.evidence_mode).metrics,
    revision_independently_validated:false,final_oos_opened:true,shadow_ready:true,shadow_started:false,
    epoch_count:0,signal_count:0,intent_count:0,fill_count:0,broker_enabled:false,real_order_path:false,
    final_oos:finalView,scientific_status:release.scientific_status,scientific_assessment:assessment,release, mapping,
    mapping_inventory:registry.industry_inventory,registry_entries:registry.entries,
    limitations:[...report.limitations,...mapping.limitations,'Final OOS has 60 overlapping H40 observations; dependence-aware uncertainty is unavailable.']};
}

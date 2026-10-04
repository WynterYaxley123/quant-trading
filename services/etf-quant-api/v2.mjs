/** Bounded, read-only V2 aggregates. No market rows, fit or runtime creation. */
import {readFile,realpath,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {repositoryFile,verifyCurrentCertificate} from '../etf-quant-runner/security-audit.mjs';

const defaultRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const CANDIDATE='strategies/etf_quant_v2/config/candidate.json';
const REPORT='reports/engineering/etf-quant-v2-build-research.json';
const MANIFEST='reports/engineering/etf-quant-v2-observation-integrity.json';
const PARENT='reports/engineering/etf-quant-v2-finalization-integrity.json';
const GRANDPARENT='reports/engineering/etf-quant-v2-build-integrity.json';
const FINAL='reports/engineering/etf-quant-v2-final-oos.json';
const RELEASE='strategies/etf_quant_v2/config/release.json';
const MAPPING='reports/engineering/etf-quant-v2-mapping-study.json';
const REGISTRY='strategies/etf_quant_v2/config/mapping-registry.json';
const sha=b=>createHash('sha256').update(b).digest('hex');
const requireValue=v=>{if(!v)throw new Error('V2_RESEARCH_INTEGRITY_BLOCKER');};

async function bounded(root,name) {
  const file=repositoryFile(root,name),s=await stat(file);
  requireValue(s.size<=512*1024);
  return readFile(file);
}
export async function observeV2(root=defaultRoot) {
  const real=await realpath(root);
  const [candidateBytes,reportBytes,manifestBytes,parentBytes]=await Promise.all([CANDIDATE,REPORT,MANIFEST,PARENT].map(n=>bounded(real,n)));
  const candidate=JSON.parse(candidateBytes),report=JSON.parse(reportBytes),manifest=JSON.parse(manifestBytes).implementation_integrity;
  const grandparentBytes=await bounded(real,GRANDPARENT);
  verifyCurrentCertificate(JSON.parse(parentBytes).implementation_integrity,JSON.parse(grandparentBytes).implementation_integrity,grandparentBytes,GRANDPARENT);
  verifyCurrentCertificate(manifest,JSON.parse(parentBytes).implementation_integrity,parentBytes,PARENT);
  // Verify every certified source, not merely report self-consistency.
  for(const [name,expected] of Object.entries(manifest.files))requireValue(sha(await readFile(repositoryFile(real,name)))===expected);
  // Python's frozen identity preserves 30.0; JS JSON normalizes it to 30.
  // The transition binds exact candidate/report bytes instead of reserializing.
  requireValue(candidate.product==='ETF_QUANT_V2' && /^[a-f0-9]{64}$/.test(candidate.candidate_sha256)
    && manifest.files[CANDIDATE]===sha(candidateBytes) && manifest.files[REPORT]===sha(reportBytes)
    && report.candidate_sha256===candidate.candidate_sha256 && candidate.validation_open_count===1
    && candidate.final_oos_opened===false && candidate.shadow_started===false && candidate.broker_enabled===false && candidate.real_order_path===false);
  const [finalBytes,releaseBytes,mappingBytes,registryBytes]=await Promise.all([FINAL,RELEASE,MAPPING,REGISTRY].map(n=>bounded(real,n)));
  for(const [name,bytes] of [[FINAL,finalBytes],[RELEASE,releaseBytes],[MAPPING,mappingBytes],[REGISTRY,registryBytes]])requireValue(manifest.files[name]===sha(bytes));
  const final=JSON.parse(finalBytes),release=JSON.parse(releaseBytes),mapping=JSON.parse(mappingBytes),registry=JSON.parse(registryBytes);
  const statuses={PASS_STRONG:'HISTORICALLY_VALIDATED_STRONG',PASS_WEAK:'HISTORICALLY_VALIDATED_WEAK',FAIL:'FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT'};
  requireValue(final.candidate_sha256===candidate.candidate_sha256 && final.open_count===1 && final.model_retuned===false
    && final.decision.scientific_status===statuses[final.decision.classification] && release.scientific_status===final.decision.scientific_status
    && release.final_oos_sha256===sha(finalBytes) && release.registry_sha256===registry.registry_sha256 && release.candidate_sha256===candidate.candidate_sha256
    && release.broker_enabled===false && release.real_order_path===false && registry.proxy_threshold===40 && registry.frozen===true);
  return {product:'ETF_QUANT_V2',research_status:release.scientific_status,candidate_sha256:candidate.candidate_sha256,
    specification:candidate.specification,evidence_mode:candidate.evidence_mode,historical_start:report.historical.start,
    historical_end:report.historical.end,trading_sessions:report.historical.trading_sessions,history_years:report.historical.history_years,
    membership_tier_rows:report.historical.membership_tier_rows,development:report.revision.selected.metrics,
    validation_status:report.validation.status,validation:report.validation.results.find(r=>r.mode===candidate.evidence_mode).metrics,
    revision_independently_validated:final.decision.classification!=='FAIL',final_oos_opened:true,shadow_ready:true,shadow_started:false,
    epoch_count:0,signal_count:0,intent_count:0,fill_count:0,broker_enabled:false,real_order_path:false,
    final_oos:final,scientific_status:release.scientific_status,release, mapping,
    mapping_inventory:registry.industry_inventory,registry_entries:registry.entries,
    limitations:[...report.limitations,...mapping.limitations,'Final OOS has 60 overlapping H40 observations; dependence-aware uncertainty is unavailable.']};
}

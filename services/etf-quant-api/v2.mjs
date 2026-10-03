/** Bounded, read-only V2 aggregates. No market rows, fit or runtime creation. */
import {readFile,realpath,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {repositoryFile,verifyCurrentCertificate} from '../etf-quant-runner/security-audit.mjs';

const defaultRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const CANDIDATE='strategies/etf_quant_v2/config/candidate.json';
const REPORT='reports/engineering/etf-quant-v2-build-research.json';
const MANIFEST='reports/engineering/etf-quant-v2-build-integrity.json';
const PARENT='reports/engineering/etf-quant-v2-integrity.json';
const sha=b=>createHash('sha256').update(b).digest('hex');
const requireValue=v=>{if(!v)throw new Error('V2_RESEARCH_INTEGRITY_BLOCKER');};

async function bounded(root,name) {
  const file=repositoryFile(root,name),s=await stat(file);
  requireValue(s.size<=256*1024);
  return readFile(file);
}
export async function observeV2(root=defaultRoot) {
  const real=await realpath(root);
  const [candidateBytes,reportBytes,manifestBytes,parentBytes]=await Promise.all([CANDIDATE,REPORT,MANIFEST,PARENT].map(n=>bounded(real,n)));
  const candidate=JSON.parse(candidateBytes),report=JSON.parse(reportBytes),manifest=JSON.parse(manifestBytes).implementation_integrity;
  verifyCurrentCertificate(manifest,JSON.parse(parentBytes).implementation_integrity,parentBytes,PARENT);
  // Verify every certified source, not merely report self-consistency.
  for(const [name,expected] of Object.entries(manifest.files))requireValue(sha(await readFile(repositoryFile(real,name)))===expected);
  // Python's frozen identity preserves 30.0; JS JSON normalizes it to 30.
  // The transition binds exact candidate/report bytes instead of reserializing.
  requireValue(candidate.product==='ETF_QUANT_V2' && /^[a-f0-9]{64}$/.test(candidate.candidate_sha256)
    && manifest.files[CANDIDATE]===sha(candidateBytes) && manifest.files[REPORT]===sha(reportBytes)
    && report.candidate_sha256===candidate.candidate_sha256 && candidate.validation_open_count===1
    && candidate.final_oos_opened===false && candidate.shadow_started===false && candidate.broker_enabled===false && candidate.real_order_path===false);
  return {product:'ETF_QUANT_V2',research_status:candidate.research_status,candidate_sha256:candidate.candidate_sha256,
    specification:candidate.specification,evidence_mode:candidate.evidence_mode,historical_start:report.historical.start,
    historical_end:report.historical.end,trading_sessions:report.historical.trading_sessions,history_years:report.historical.history_years,
    membership_tier_rows:report.historical.membership_tier_rows,development:report.revision.selected.metrics,
    validation_status:report.validation.status,validation:report.validation.results.find(r=>r.mode===candidate.evidence_mode).metrics,
    revision_independently_validated:false,final_oos_opened:false,shadow_ready:true,shadow_started:false,
    epoch_count:0,signal_count:0,intent_count:0,fill_count:0,broker_enabled:false,real_order_path:false,
    limitations:report.limitations};
}

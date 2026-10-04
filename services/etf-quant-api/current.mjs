/** Read-only projection of certified release metadata and the actual control receipt.
 * No model, mapping, accounting, source refresh or runtime mutation lives here.
 */
import { readFile, realpath, stat, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { observeV2 } from './v2.mjs';

export const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HASH = /^[a-f0-9]{64}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const digest = raw => createHash('sha256').update(raw).digest('hex');
const check = v => { if (!v) throw new Error('CURRENT_STATUS_INTEGRITY_BLOCKER'); };
async function external(root) {
  check(path.isAbsolute(root));
  const resolved = await realpath(root);
  for (let p=resolved;;p=path.dirname(p)) {
    try { await access(path.join(p,'.git')); throw new Error('REPO_ROOT_FORBIDDEN'); }
    catch(e) { if(e.code !== 'ENOENT') throw e; }
    if(path.dirname(p)===p) break;
  }
  return resolved;
}
async function leaf(root, relative, limit=1024*1024) {
  const file=await realpath(path.join(root,relative));
  const remaining=path.relative(root,file);
  check(remaining && !remaining.startsWith('..') && !path.isAbsolute(remaining));
  const info=await stat(file);
  check(info.isFile() && info.size<=limit);
  return {raw:await readFile(file),mtime:info.mtime.toISOString()};
}
const json = item => JSON.parse(item.raw);
export function calendarState(raw, now) {
  // Calendar CSV dates and booleans occupy the first schema columns, before
  // provenance. Quoted field splitting also accepts a standard CSV writer.
  const lines=raw.toString('utf8').trim().split(/\r?\n/);
  const fields=line=>[...line.matchAll(/(?:^|,)("(?:[^"]|"")*"|[^,]*)/g)]
    .map(m=>m[1].replace(/^"|"$/g,'').replaceAll('""','"'));
  const header=fields(lines.shift());
  const di=header.indexOf('trade_date'),ti=header.indexOf('is_trading');
  check(di>=0 && ti>=0 && lines.length<20000);
  const calendar=new Map();
  for(const line of lines) {
    const row=fields(line),day=row[di],trading=row[ti];
    check(DATE.test(day) && ['true','false'].includes(trading) && !calendar.has(day));
    calendar.set(day,trading==='true');
  }
  const local=new Date(now+8*3600000).toISOString(),today=local.slice(0,10);
  check(calendar.has(today));
  const beforeClose=local.slice(11,16)<'15:05';
  const eligible=[...calendar].filter(([d,t])=>t && (d>today || d===today && beforeClose)).map(([d])=>d).sort();
  return {as_of_shanghai:local.replace('Z','+08:00'),today,is_trading:calendar.get(today),
    market_state:!calendar.get(today)?'HOLIDAY':beforeClose?'WAITING_FOR_MARKET_CLOSE':'AFTER_FINALIZATION_TIME',
    next_eligible_trading_date:eligible[0]??null};
}
export function unconfiguredCurrent(now) {
  return {contract:'CURRENT_ETF_QUANT_STATUS_V1',observed_at:new Date(now).toISOString(),project:'ETF-Quant V1',
    mode:'SIMULATION_ONLY',read_only:true,engineering_complete:false,production_usable:false,
    factual_pipeline:'UNKNOWN',model_readiness:{status:'UNKNOWN',as_of:null,horizons:{}},
    shadow_runtime_armed:false,shadow_start_gate:'NOT_CONFIGURED',latest_finalized_market_date:null,snapshot_id:null,
    calendar:null,runner:null,formal:{epoch_id:null,signal_date:null,t1_status:null,epoch_count:0,signal_count:0,
      intent_count:0,fill_count:0,holdings_count:0,cash_weight:null,risk_asset_weight:null,nav:null,pnl:null},
    provenance:{code_sha:null,release_code_sha:null,candidate_hash:null,pit_registry_hash:null,strict_registry_hash:null,cnequity_pin:null},
    evidence:{production_pit:'UNKNOWN',strict_registry:'UNKNOWN',sws:'UNKNOWN',known_limitation:null},
    historical_status:null,one_shot_command:null,release_as_of:null,broker_enabled:false,real_order_path:false};
}
export async function aggregateCurrent({controlRoot,view,pointer=null,now=Date.now(),repoRoot=REPO}) {
  if(!controlRoot) return unconfiguredCurrent(now);
  const root=await external(controlRoot);
  const releaseFile=await leaf(repoRoot,'reports/etf_quant/etf_quant_v1_final_release_v1.json');
  const release=json(releaseFile);
  check(release.project==='ETF-Quant V1' && release.mode==='SIMULATION_ONLY'
    && release.broker_enabled===false && release.real_order_path===false
    && Number.isFinite(Date.parse(release.generated_at)) && Date.parse(release.generated_at)<=now);
  for(const [name,field] of [
    ['reports/etf_quant/etf_quant_v1_proxy_final_candidate_manifest.json','candidate_hash'],
    ['reports/etf_quant/production_pit_evidence_registry_v1.json','pit_registry_hash'],
    ['strategies/etf_quant/config/verified_mappings_v1.json','strict_registry_hash']]) {
    check(HASH.test(release[field]) && release.certified_files[name]===release[field]);
  }
  let transition;
  for(const [name,hash] of Object.entries(release.certified_files)) {
    check(HASH.test(hash) && !path.isAbsolute(name) && !name.split(/[\\/]/).includes('..'));
    const currentHash=digest((await leaf(repoRoot,name)).raw);
    if(currentHash===hash) continue;
    check(['services/etf-quant-api/server.mjs','services/etf-quant-api/current.mjs'].includes(name));
    if(!transition) {
      await observeV2(repoRoot); // Verify the complete current certificate and its immutable parent.
      transition=json(await leaf(repoRoot,'reports/engineering/etf-quant-v2-observation-integrity.json')).implementation_integrity;
      check(transition.v1_observation_transition.release_manifest_sha256===digest(releaseFile.raw));
    }
    const change=transition.v1_observation_transition.files[name];
    check(transition.files[name]===currentHash && change?.before_sha256===hash && change.after_sha256===currentHash);
  }
  const observationFile=await leaf(root,'latest_observation.json',128*1024);
  const observation=json(observationFile);
  check(typeof observation.status==='string' && /^[A-Z0-9_]+$/.test(observation.status)
    && typeof observation.shadow_runtime_armed==='boolean'
    && ['STARTED','ARMED_FOR_NEXT_ELIGIBLE_T','BLOCKED_HARD'].includes(observation.shadow_start_gate));
  const pointerRaw=(await leaf(root,'latest_export.json',8192)).raw;
  const exported=JSON.parse(pointerRaw);
  check(HASH.test(exported.snapshot_id) && HASH.test(exported.manifest_sha256));
  const exportName=`exports/${exported.snapshot_id}`;
  const manifestRaw=(await leaf(root,`${exportName}/manifest.json`)).raw;
  check(digest(manifestRaw)===exported.manifest_sha256);
  const manifest=JSON.parse(manifestRaw);
  check(manifest.snapshot_id===exported.snapshot_id && DATE.test(manifest.data_cutoff)
    && manifest.source_commit===release.cnequity_pin && Date.parse(manifest.created_at)<=now);
  const calendarRaw=(await leaf(root,`${exportName}/trading_calendar.csv`,4*1024*1024)).raw;
  check(digest(calendarRaw)===manifest.files['trading_calendar.csv']);
  const calendar=calendarState(calendarRaw,now);
  check(manifest.data_cutoff<=calendar.today);
  const codeSha=(await promisify(execFile)('git',['rev-parse','HEAD'],{cwd:repoRoot})).stdout.trim();
  check(/^[a-f0-9]{40}$/.test(codeSha));
  const epoch=view.status.shadow_epoch??null,signal=view.status.formal_signal??null;
  if(epoch) check(epoch.candidate_hash===release.candidate_hash
    && signal.pit_registry_hash===release.pit_registry_hash && signal.strict_registry_hash===release.strict_registry_hash);
  // The verified formal namespace wins over a stale pre-start delivery record.
  const started=!!epoch;
  const failed=view.health.last_attempt_status==='FAILED';
  const superseded=failed && release.superseded_failure_codes?.includes(view.health.blockers[0])
    && Date.parse(view.health.last_attempt_at)<=Date.parse(release.superseded_before);
  const armed=release.production_usable===true && observation.shadow_runtime_armed && (!failed || superseded);
  const matchesRun=pointer && observation.run_id===pointer.run_id;
  const intentCount=!started?0:matchesRun && Number.isInteger(observation.intent_count)?observation.intent_count:null;
  const result={...unconfiguredCurrent(now),engineering_complete:release.engineering_complete===true,
    production_usable:release.production_usable===true,factual_pipeline:release.factual_pipeline,
    model_readiness:release.model_readiness,release_as_of:release.as_of,
    latest_finalized_market_date:manifest.data_cutoff,snapshot_id:exported.snapshot_id,calendar,
    shadow_runtime_armed:armed,shadow_start_gate:started?'STARTED':failed && !superseded?'BLOCKED_INTEGRITY':observation.shadow_start_gate,
    runner:{status:observation.status,observed_at:observation.processed_at??observationFile.mtime,
      time_source:observation.processed_at?'RECEIPT':'RECEIPT_FILE_MTIME',data_cutoff:observation.data_cutoff??null,
      refresh_attempted:observation.refresh?.refresh_attempted??false,reason_code:observation.reason_code??null,
      next_action:started?signal.t1_status:armed?'RUN_ONE_SHOT_ON_NEXT_ELIGIBLE_FINALIZED_T':'CHECK_INTEGRITY'},
    formal:{epoch_id:epoch?.epoch_id??null,signal_date:signal?.signal_date??null,t1_status:signal?.t1_status??null,
      epoch_count:started?1:0,signal_count:signal?1:0,intent_count:intentCount,fill_count:view.trades.length,
      holdings_count:view.holdings.length,cash_weight:signal?.cash_weight??null,risk_asset_weight:signal?.risk_asset_weight??null,
      nav:view.nav.at(-1)?.normalized_nav??null,pnl:view.portfolio_summary.total_pnl,
      count_scope:'CURRENT_COMMITTED_FORMAL_VIEW'},
    provenance:{code_sha:codeSha,release_code_sha:release.code_sha,candidate_hash:release.candidate_hash,
      pit_registry_hash:release.pit_registry_hash,strict_registry_hash:release.strict_registry_hash,cnequity_pin:release.cnequity_pin},
    evidence:release.evidence,one_shot_command:release.one_shot_command,
    historical_status:superseded?{
      status:'SUPERSEDED / HISTORICAL',reason_code:view.health.blockers[0]??null,
      processed_at:view.health.last_attempt_at??null}:null};
  // Compare pointers/receipt again: do not combine two concurrent generations.
  check((await leaf(root,'latest_export.json',8192)).raw.equals(pointerRaw)
    && (await leaf(root,'latest_observation.json',128*1024)).raw.equals(observationFile.raw));
  return result;
}
export function projectCurrent(view,current) {
  if(!current.shadow_runtime_armed || view.status.shadow_epoch) return;
  view.status={...view.status,phase:'ARMED',reason:'WAITING_FOR_NEXT_ELIGIBLE_FINALIZED_T',
    cutoff:current.latest_finalized_market_date,snapshot_id:current.snapshot_id,
    code_commit:current.provenance.code_sha,source_commit:current.provenance.cnequity_pin,
    updated_at:current.runner.observed_at};
  view.health={...view.health,status:'ARMED',blockers:[],current_status:'ARMED_FOR_NEXT_ELIGIBLE_T'};
  delete view.health.last_attempt_status;
  delete view.health.last_attempt_at;
  if(!view.mappings.slots) view.mappings={...view.mappings,status:'AWAITING_FORMAL_SIGNAL',
    reason:'NO_FORMAL_SHADOW_SIGNAL_YET'};
}

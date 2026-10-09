/** Verified public aggregates and one pinned private historical preview. No numerical source reader. */
import {createHash} from 'node:crypto';
import {realpath,access} from 'node:fs/promises';
import path from 'node:path';
import {isDeepStrictEqual} from 'node:util';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {boundedLeaf} from '../etf-quant-api/bounded.mjs';
import {verifiedResearchFiles} from './evidence.mjs';

const SPEC='config/research/swl1-rev10-short-v1.json';
const REPORTS='reports/research/swl1_short_horizon_exploration/';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const LOADED_SOURCE_SHA=sha(readFileSync(fileURLToPath(import.meta.url)));
const check=v=>{if(!v)throw new Error('REV10_INTEGRITY_BLOCKER');};
const parse=bytes=>JSON.parse(bytes.toString());
const HASH=/^[a-f0-9]{64}$/;
export const CHARTS={
  'signal-rankic':'信号与 H5 / H10 RankIC', 'temporal-blocks':'四个固定时间块',
  'ridge-comparison':'简单反转与 Ridge', 'factor-target-correlations':'因子与目标相关性',
  'industry-sensitivity':'30 行业敏感性', 'concentration-turnover':'集中度与换手',
};
export const EVIDENCE={
  design:'config/research/swl1-short-horizon-exploratory-design.json',
  'chinese-report':'docs/research/swl1-short-horizon-exploration.zh-CN.md',
  acceptance:'docs/engineering/swl1-rev10-acceptance.md',
  'data-boundary':REPORTS+'data-boundary.json',
  'research-decision':REPORTS+'research-decision.json',
  'source-qualification':'docs/research/swl1-real-data-source-qualification.zh-CN.md',
  'preregistration-draft':'docs/research/swl1-rev10-preregistration-draft.zh-CN.md',
};

async function publicContext(root) {
  const files=await verifiedResearchFiles(root);
  const read=async name=>{const raw=(await boundedLeaf(root,name,2*1024*1024)).raw;check(files[name]===sha(raw));return raw;};
  const specRaw=await read(SPEC),spec=parse(specRaw);
  const universe=parse(await read(spec.universe_file));
  check(sha(await read(spec.universe_file))===spec.universe_sha256 && universe.industries.length===30);
  check(spec.model_type==='FIXED_RULE' && spec.training_required===false && spec.lookback===10 && spec.primary_horizon===10 && spec.secondary_horizon===5 && spec.formal_preregistration_active===false && spec.production_source_admitted===false);
  return {files,read,spec,modelHash:sha(specRaw),universe};
}

export async function overview(root) {
  const {read,spec,modelHash}=await publicContext(root);
  const summary=parse(await read(REPORTS+'research-summary.json'));
  const boundary=parse(await read(REPORTS+'data-boundary.json'));
  const decision=parse(await read(REPORTS+'research-decision.json'));
  const readiness=parse(await read('reports/research/swl1_source_qualification/final-readiness.json'));
  check(summary.label==='EXPLORATORY_POST_HOC_RESEARCH' && summary.formal_validation===false && boundary.last_outcome===spec.historical_cutoff && boundary.unseen_outcomes_read===false && readiness.real_sources_admitted===0 && readiness.research_readiness==='DATA_SOURCE_NOT_READY');
  const models={};
  for(const id of ['S0','S1','S2','S3','S4']) {
    models[id]={};
    for(const h of ['5','10']) {
      const m=summary.models[id][h];
      models[id][h]={rank_ic:m.rank_ic,signal_count:m.signal_count,calendar_blocks:m.calendar_blocks,raw_spread:m.raw_top5_minus_bottom5_spread};
    }
  }
  return {
    model:spec,model_hash:modelHash,classification:'EXPLORATORY_POST_HOC',historical_cutoff:boundary.last_outcome,
    models,decision:decision.decision,limitations:decision.limitations,
    readiness:{model_implemented:true,historical_exploration_available:true,preregistration_draft_ready:true,
      formal_preregistration_active:false,production_source_admitted:false,production_signature_authority:readiness.production_authority,
      statistical_design:'STATISTICAL_DESIGN_PENDING',prospective_observations_collected:0,independent_validation_complete:false,
      data_status:readiness.research_readiness,real_sources_admitted:readiness.real_sources_admitted,
      historical_access_isolation:readiness.historical_access_isolation,certified_historically_unseen_sessions:0,
      swl1_v1:'FAILED_VALIDATION',swl1_v2:'FAILED_VALIDATION',final_oos_opened:false},
    charts:Object.entries(CHARTS).map(([id,title])=>({id,title})),
    evidence:Object.entries(EVIDENCE).map(([id,reference])=>({id,reference})),
    research_pr:'https://github.com/WynterYaxley123/quant-trading/pull/36',
    source_hashes:{summary:sha(await read(REPORTS+'research-summary.json')),boundary:sha(await read(REPORTS+'data-boundary.json'))},
  };
}

export async function privateRanking(root,previewRoot='',manifestPin='') {
  const unavailable={status:'UNAVAILABLE',reason:'LOCAL_PRIVATE_REPLAY_NOT_CONFIGURED',asof:null,count:0,rows:[],top5:[],bottom5:[]};
  if(!previewRoot && !manifestPin)return unavailable;
  check(path.isAbsolute(previewRoot) && HASH.test(manifestPin));
  const base=await realpath(previewRoot);check(base===path.resolve(previewRoot) && path.basename(base)==='preview');
  for(let p=base;;p=path.dirname(p)) {
    try {await access(path.join(p,'.git'));throw new Error('REV10_INTEGRITY_BLOCKER');}
    catch(e){if(e.code!=='ENOENT')throw e;}
    if(path.dirname(p)===p)break;
  }
  const {spec,modelHash,universe}=await publicContext(root);
  const read=async name=>(await boundedLeaf(base,name,128*1024)).raw;
  const manifestRaw=await read('manifest.json');check(sha(manifestRaw)===manifestPin);
  const manifest=parse(manifestRaw);
  check(manifest.namespace==='RESEARCH_REPLAY_ONLY' && manifest.model_hash===modelHash && manifest.count===30 && manifest.asof<=spec.historical_cutoff && manifest.source_commit===spec.source_commit);
  check(Object.keys(manifest.files).sort().join('|')==='observation.json|ranking.json|scores.json');
  const artifacts={};
  for(const [name,hash] of Object.entries(manifest.files)) {const raw=await read(name);check(sha(raw)===hash);artifacts[name]=parse(raw);}
  for(const [name,hash] of Object.entries(manifest.implementation_sha256)) {
    check(['model.py','replay.py'].includes(name) && sha((await boundedLeaf(root,`research/swl1_rev10_short_v1/${name}`,64*1024)).raw)===hash);
  }
  check(Object.keys(manifest.implementation_sha256).sort().join('|')==='model.py|replay.py');
  const observation=artifacts['observation.json'],ranking=artifacts['ranking.json'],scores=artifacts['scores.json'];
  check(observation.status==='HISTORICAL_REPLAY' && observation.namespace==='RESEARCH_REPLAY_ONLY' && observation.formal_forecast===false && observation.future_numeric_rows_read===0 && observation.asof===manifest.asof && observation.cutoff===spec.historical_cutoff && observation.names_reference_sha256===spec.universe_sha256 && isDeepStrictEqual(observation.input_sha256,spec.view_sha256));
  const window=observation.window_sessions;
  check(Array.isArray(window) && window.length===10 && window.at(-1)===manifest.asof && window.every((day,i)=>/^\d{4}-\d{2}-\d{2}$/.test(day) && Number.isFinite(Date.parse(day)) && new Date(day).toISOString().slice(0,10)===day && (!i||window[i-1]<day)));
  check(ranking.status==='HISTORICAL_REPLAY' && ranking.namespace==='RESEARCH_REPLAY_ONLY' && ranking.complete_universe===true && ranking.count===30 && ranking.asof===manifest.asof && ranking.rows.length===30);
  check(ranking.ranking_basis==='REV10_DESCENDING_CODE_ASCENDING_TIES');
  const names=new Map(universe.metadata.map(r=>[r.code,r.name]));
  const codes=ranking.rows.map(r=>r.industry_code);
  check(isDeepStrictEqual([...codes].sort(),universe.industries));
  const rawMean=ranking.rows.reduce((n,r)=>n+r.rev10_score,0)/30;
  for(const [i,r] of ranking.rows.entries()) {
    check(Object.keys(r).sort().join('|')==='data_asof|data_completeness|industry_code|industry_name|name_verified|rank|relative_score|rev10_score|source_generation|trailing_mean_return');
    check(r.rank===i+1 && [r.rev10_score,r.relative_score,r.trailing_mean_return].every(Number.isFinite));
    check(r.data_asof===manifest.asof && r.data_completeness==='10_OF_10_FINITE_SESSIONS' && r.source_generation===observation.source_generation);
    check(r.name_verified===Boolean(names.get(r.industry_code)) && r.industry_name===(names.get(r.industry_code)||r.industry_code));
    check(Math.abs(r.rev10_score+r.trailing_mean_return)<1e-12 && Math.abs(r.relative_score-(r.rev10_score-rawMean))<1e-12);
    if(i) {const p=ranking.rows[i-1];check(p.rev10_score>r.rev10_score || p.rev10_score===r.rev10_score && p.industry_code<r.industry_code);}
  }
  const byCode=[...ranking.rows].sort((a,b)=>a.industry_code.localeCompare(b.industry_code));
  const bottom=[...ranking.rows].sort((a,b)=>a.rev10_score-b.rev10_score||a.industry_code.localeCompare(b.industry_code)).slice(0,5);
  check(isDeepStrictEqual(scores.rows,byCode) && isDeepStrictEqual(ranking.top5,ranking.rows.slice(0,5)) && isDeepStrictEqual(ranking.bottom5,bottom));
  return {...ranking,manifest_sha256:manifestPin,source_commit:spec.source_commit,source_generation:observation.source_generation,window_sessions:observation.window_sessions};
}

export async function rev10Resource(root,resource,{previewRoot='',manifestPin='',serverSourceHash=''}={}) {
  if(resource==='overview')return {data:await overview(root)};
  if(resource==='ranking')return {data:await privateRanking(root,previewRoot,manifestPin)};
  if(resource==='health') {const {modelHash}=await publicContext(root);return {data:{service:'SWL1_REV10_READ_ONLY_RESEARCH',read_only:true,model_hash:modelHash,module_sha256:LOADED_SOURCE_SHA,server_module_sha256:serverSourceHash,preview_configured:Boolean(previewRoot),manifest_sha256:manifestPin||null}};}
  const {read}=await publicContext(root);
  if(resource.startsWith('chart/')) {
    const id=resource.slice(6);check(Object.hasOwn(CHARTS,id));
    const raw=await read(REPORTS+id+'.svg');check(!/<script|<image/i.test(raw.toString()));
    return {raw,contentType:'image/svg+xml; charset=utf-8'};
  }
  if(resource.startsWith('evidence/')) {
    const id=resource.slice(9);check(Object.hasOwn(EVIDENCE,id));
    return {raw:await read(EVIDENCE[id]),contentType:'text/plain; charset=utf-8'};
  }
  throw new Error('INVALID_RESOURCE');
}

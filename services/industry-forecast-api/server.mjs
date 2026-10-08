/** Canonical SWL2 observer. Built-in Node only, closed routes, no writes or fitting. */
import http from 'node:http';
import {createHash} from 'node:crypto';
import {realpath, access} from 'node:fs/promises';
import {isDeepStrictEqual} from 'node:util';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {boundedLeaf, containedExists} from '../etf-quant-api/bounded.mjs';
import {allowedOrigins} from '../etf-quant-api/origins.mjs';
import {canonicalJSON, verifyCurrentCertificate, certificateHash} from '../etf-quant-runner/security-audit.mjs';
import {publicEvidence} from './evidence.mjs';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const ACTIVE='reports/engineering/swl1-data-first-integrity.json';
const PARENT='reports/engineering/shadow-task-installation-integrity.json';
const REGISTRY='config/research/swl2-ridge-families.json';
const HASH=/^[a-f0-9]{64}$/, COMMIT=/^[a-f0-9]{40}$/;
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const check=value=>{if(!value)throw new Error('FORECAST_INTEGRITY_BLOCKER');};
const read=async(root,name,limit=1024*1024)=>(await boundedLeaf(root,name,limit)).raw;
const json=raw=>JSON.parse(raw.toString());
const mean=xs=>xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null;
const median=xs=>{if(!xs.length)return null;xs=[...xs].sort((a,b)=>a-b);const i=Math.floor(xs.length/2);return xs.length%2?xs[i]:(xs[i-1]+xs[i])/2;};

export function validateV2(f,artifacts) {
  const {protocol_reference:p,status_reference:s,frozen_universe_reference:u,candidate_reference:c,validation_reference:v,development_reference:d}=artifacts;
  const hash=f.protocol_reference.sha256,w=s.public_preregistration_anchor.external_merge_witness;
  check(f.family_id==='swl1_ridge_v2' && f.display_name==='SWL1-Ridge-V2' && f.generation===2 && f.industry_level===1 && f.current_role==='INDUSTRY_FORECAST_RESEARCH' && f.etf_productization_status==='NOT_STARTED');
  check(['NO_DEVELOPMENT_CANDIDATE','FAILED_VALIDATION','AWAITING_PROSPECTIVE_FINAL_OOS','VALIDATION_INTERVAL_NOT_UNSEEN','NOT_RESEARCHABLE_WITH_CURRENT_DATA'].includes(s.scientific_status) && f.scientific_status===s.scientific_status);
  check(f.forward_eligible===false && s.forward_eligible===false && s.final_oos_opened===false && s.final_oos_consumed===false && s.validation_reopened===false && s.validation_informed_revision===false && s.formal_forward_forecasts_created===0 && s.live_scheduler_enabled===false && s.live_deployment_promoted===false);
  check(p.family_id===f.family_id && s.protocol_hash===hash && p.primary_series==='RECONSTRUCTED_SWL1_EQUAL_WEIGHT' && p.final_oos_mode==='PROSPECTIVE_ONLY' && p.model_universe_hash===f.frozen_universe_reference.sha256 && isDeepStrictEqual(p.model_universe,u.industries) && isDeepStrictEqual(u.industries,f.industry_codes));
  check(w.protocol_hash===hash && w.merged===true && w.exact_remote_bytes_verified===true && w.factual_performance_before_remote_anchor===false);
  if(d)check(d.protocol_hash===hash && d.leaderboard.length===16 && p.specifications.length===16);
  if(c)check(c.protocol_hash===hash && s.candidate_hash===f.candidate_reference.sha256 && f.model_contract_hash===s.candidate_hash && c.model_universe_hash===f.frozen_universe_reference.sha256 && isDeepStrictEqual(c.implementation_hashes,p.implementation_hashes));
  else check(s.candidate_hash==null && f.model_contract_hash===hash);
  if(['FAILED_VALIDATION','AWAITING_PROSPECTIVE_FINAL_OOS'].includes(s.scientific_status)) {
    check(c && v && d);
    check(v.lineage.protocol_hash===hash && v.lineage.candidate_hash===s.candidate_hash && v.passed===(s.scientific_status==='AWAITING_PROSPECTIVE_FINAL_OOS') && s.validation_opened===true && s.validation_passed===v.passed);
  } else {
    check(!c && !v && s.validation_opened===false);
    if(s.scientific_status==='NO_DEVELOPMENT_CANDIDATE')check(d && d.leaderboard.every(row=>row.admitted===false));
  }
}

export async function families(repoRoot=ROOT) {
  const [raw,parentRaw,registryRaw]=await Promise.all([ACTIVE,PARENT,REGISTRY].map(n=>read(repoRoot,n)));
  const parent=json(parentRaw).implementation_integrity;
  check(parent.certificate_sha256===certificateHash(parent));
  const manifest=verifyCurrentCertificate(json(raw).implementation_integrity,parent,parentRaw,PARENT);
  // Verify source bytes, including registry and adapters; never parse performance records.
  const entries=Object.entries(manifest.files);
  for(let i=0;i<entries.length;i+=8)await Promise.all(entries.slice(i,i+8).map(async([name,hash])=>check(sha(await read(repoRoot,name,2*1024*1024))===hash)));
  check(manifest.files[REGISTRY]===sha(registryRaw));
  const result=json(registryRaw).families;
  check(result.length===2);
  for(const [i,f] of result.entries()) {
    check(f.family_id===`swl2_ridge_v${i+1}` && f.display_name===`SWL2-Ridge-V${i+1}` && f.current_role==='INDUSTRY_FORECAST_RESEARCH' && f.etf_productization_status==='RETIRED');
    const [universe,taxonomy]=await Promise.all(['frozen_universe_reference','taxonomy_reference'].map(async key=>{const ref=f[key],bytes=await read(repoRoot,ref.path);check(sha(bytes)===ref.sha256);return json(bytes);}));
    const codes=universe.industries;
    check(isDeepStrictEqual(codes,[...new Set(codes)].sort()) && isDeepStrictEqual(codes,f.industry_codes));
    if(f.generation===2)check(universe.source_metadata_sha256===f.frozen_model_reference.warmup_metadata_sha256 && universe.warmup_panel_sha256===f.frozen_model_reference.warmup_panel_sha256);
    const current=taxonomy.industries.filter(r=>r.vintage===taxonomy.classification_version).map(r=>r.industry_code).sort();
    check(taxonomy.taxonomy_identity===f.taxonomy_identity && codes.every(c=>current.includes(c)));
    Object.assign(f,{taxonomy_scope:taxonomy.classification_version,taxonomy_universe_size:current.length,legacy_taxonomy_identity_count:taxonomy.industries.length-current.length,model_universe_size:codes.length,model_universe_hash:sha(JSON.stringify(codes)),taxonomy_only_industries:current.filter(c=>!codes.includes(c)),taxonomy_only_status:'NOT_IN_FROZEN_MODEL_UNIVERSE'});
  }
  const catalogRaw=await read(repoRoot,'config/research/industry-forecast-families.json');
  check(manifest.files['config/research/industry-forecast-families.json']===sha(catalogRaw));
  const catalog=json(catalogRaw);check(catalog.swl2_registry_reference.path===REGISTRY && catalog.swl2_registry_reference.sha256===sha(registryRaw));
  for(const reference of catalog.additional_families) {
    const bytes=await read(repoRoot,reference.path);check(sha(bytes)===reference.sha256);
    const f=json(bytes),artifacts={};
    for(const key of ['protocol_reference','candidate_reference','taxonomy_reference','frozen_universe_reference','validation_reference','status_reference','development_reference'].filter(key=>f[key]!=null)) {
      const ref=f[key],raw=await read(repoRoot,ref.path);check(sha(raw)===ref.sha256);artifacts[key]=json(raw);
    }
    const {protocol_reference:protocol,candidate_reference:candidate,taxonomy_reference:taxonomy,frozen_universe_reference:universe,validation_reference:validation,status_reference:status}=artifacts;
    if(f.family_id==='swl1_ridge_v2')validateV2(f,artifacts);
    else {
    check(f.family_id==='swl1_ridge_v1' && f.display_name==='SWL1-Ridge-V1' && f.industry_level===1 && f.generation===1 && f.current_role==='INDUSTRY_FORECAST_RESEARCH' && f.etf_productization_status==='NOT_STARTED');
    check(f.scientific_status==='FAILED_VALIDATION' && status.scientific_status===f.scientific_status && f.forward_eligible===false && status.forward_eligible===false && validation.passed===false && status.final_oos_opened===false);
    check(candidate.protocol_hash===f.protocol_reference.sha256 && status.protocol_hash===f.protocol_reference.sha256 && validation.lineage.protocol_hash===f.protocol_reference.sha256 && validation.lineage.candidate_hash===f.candidate_reference.sha256 && status.candidate_hash===f.candidate_reference.sha256 && f.model_contract_hash===f.candidate_reference.sha256);
    check(candidate.model_universe_hash===f.frozen_universe_reference.sha256 && protocol.model_universe_hash===f.frozen_universe_reference.sha256 && protocol.taxonomy_hash===f.taxonomy_reference.sha256);
    check(isDeepStrictEqual(universe.industries,f.industry_codes) && isDeepStrictEqual(protocol.model_universe,f.industry_codes));
    }
    const current=taxonomy.industries.map(r=>r.industry_code).sort(),codes=f.industry_codes;
    check(isDeepStrictEqual(codes,[...new Set(codes)].sort()) && codes.every(c=>current.includes(c)));
    Object.assign(f,{taxonomy_scope:taxonomy.classification_version,taxonomy_universe_size:current.length,model_universe_size:codes.length,model_universe_hash:sha(JSON.stringify(codes)),taxonomy_only_industries:current.filter(c=>!codes.includes(c)),taxonomy_only_status:'NOT_IN_FROZEN_MODEL_UNIVERSE'});
    if(f.family_id==='swl1_ridge_v2')Object.assign(f,{
      protocol_hash:f.protocol_reference.sha256,candidate_hash:status.candidate_hash??null,
      validation_status:status.validation_opened?(status.validation_passed?'PASS':'FAIL'):'NOT_OPENED',
      final_oos_status:'PROSPECTIVE_NOT_OPENED',membership_confidence:protocol.membership_confidence,primary_series:protocol.primary_series,
      research_evidence:{ranges:protocol.split.ranges,development:artifacts.development_reference??null,validation:validation??null,selected_spec:candidate?.spec??null,anchor:status.public_preregistration_anchor.external_merge_witness},
    });
    result.push(f);
  }
  return result;
}

async function externalRoot(root) {
  check(path.isAbsolute(root));
  const real=await realpath(root);check(path.relative(path.resolve(root),real)==='');
  for(let p=real;;p=path.dirname(p)) {
    try {await access(path.join(p,'.git'));throw new Error('FORECAST_INTEGRITY_BLOCKER');}
    catch(e){if(e.code!=='ENOENT')throw e;}
    if(path.dirname(p)===p)break;
  }
  check(path.basename(real)==='industry-forecast');
  return real;
}

const DATE=/^\d{4}-\d{2}-\d{2}$/;
const local=stamp=>new Date(Date.parse(stamp)+8*3600000).toISOString();
function safe(value,depth=0) {
  check(depth<40);
  if(typeof value==='number')check(Number.isFinite(value));
  if(typeof value==='string')check(value.length<8*1024*1024 && !/^(?:[A-Za-z]:[\\/]|file:|\/|\\\\)/.test(value));
  if(value && typeof value==='object')for(const [key,child] of Object.entries(value)){
    check(!/^(cash|initial_capital|account_value|position|positions|position_value|target_position|lot_size|etf_code|etf_mapping|intent|intents|nav|fills?|orders?|shares|commission|slippage|token|password|secret|api_key|credentials|private_key)$/i.test(key));safe(child,depth+1);
  }
}
export function validateEvents(events,binding,family,now=Date.now()) {
  check(Array.isArray(events) && events.length<=10000 && binding.family_id===family.family_id && binding.model_contract_hash===family.model_contract_hash && COMMIT.test(binding.source_commit) && COMMIT.test(binding.merge_commit));
  check(Number.isFinite(Date.parse(binding.freeze_at)) && Date.parse(binding.freeze_at)<=now && Date.parse(binding.merge_at)<=Date.parse(binding.freeze_at));
  let previous=null;const ids=new Set(),published=new Map(),evaluated=new Set();
  for(const e of events) {
    check(Object.keys(e).sort().join('|')==='body|body_hash|body_json|event_id|previous_hash');
    check(e.previous_hash===previous && HASH.test(e.body_hash) && sha(e.body_json)===e.body_hash && isDeepStrictEqual(json(e.body_json),e.body) && !ids.has(e.event_id));
    const b=e.body;safe(b);
    check(b.schema_version===1 && b.family_id===family.family_id && b.model_contract_hash===binding.model_contract_hash && b.source_commit===binding.source_commit && DATE.test(b.signal_date));
    const boundary=new Date(Math.max(Date.parse(binding.merge_at),Date.parse(binding.freeze_at))+8*3600*1000).toISOString().slice(0,10);
    check(b.signal_date>boundary && b.taxonomy_identity===family.taxonomy_identity && b.target_contract==='SAME_DATE_CROSS_SECTION_EXCESS_INDUSTRY_RETURN');
    if(b.kind==='FORECAST') {
      check(!published.has(b.signal_date) && b.display_name===family.display_name && b.legacy_identity===family.legacy_identity && b.data_cutoff===b.signal_date && Date.parse(b.published_at)<=now);
      check(new Date(Date.parse(b.published_at)+8*3600*1000).toISOString().slice(0,10)===b.signal_date);
      check(b.model_universe_hash===family.model_universe_hash && b.model_universe_size===family.model_universe_size && b.taxonomy_universe_size===family.taxonomy_universe_size && b.forecast_row_count===b.industry_count && isDeepStrictEqual(b.transition_binding,binding) && b.realized_series_type==='RECONSTRUCTED_SWL2_EQUAL_WEIGHT');
      check(Array.isArray(b.cross_section) && b.cross_section.length===family.industry_codes.length && b.industry_count===b.cross_section.length && isDeepStrictEqual(b.horizons,[10,40,120]));
      check(new Set(b.cross_section.map(r=>r.industry_code)).size===b.industry_count && b.cross_section.every((r,i)=>family.industry_codes.includes(r.industry_code) && r.fused_rank===i+1 && typeof r.industry_name==='string' && Number.isFinite(r.fused_score) && ['10','40','120'].every(h=>Number.isFinite(r.horizons[h].raw_prediction) && Number.isFinite(r.horizons[h].cross_section_zscore) && Number.isInteger(r.horizons[h].rank))));
      for(const h of ['10','40','120'])check(new Set(b.cross_section.map(r=>r.horizons[h].rank)).size===b.industry_count && b.cross_section.every(r=>r.horizons[h].rank>=1 && r.horizons[h].rank<=b.industry_count));
      check(b.provenance.realized_series_type==='RECONSTRUCTED_SWL2_EQUAL_WEIGHT' && Date.parse(b.provenance.available_at)<=Date.parse(b.published_at));
      check(b.provenance.data_cutoff===b.signal_date && local(b.published_at).slice(0,10)===b.signal_date && local(b.published_at).slice(11,16)>='15:05' && local(b.provenance.available_at).slice(0,10)===b.signal_date && local(b.provenance.available_at).slice(11,16)>='15:05');
      published.set(b.signal_date,{body:b,hash:e.body_hash});
    } else {
      const forecast=published.get(b.signal_date),id=`${b.signal_date}_${b.horizon}`;
      check(b.kind==='EVALUATION' && forecast && b.forecast_hash===forecast.hash && [10,40,120].includes(b.horizon) && !evaluated.has(id));
      check(Array.isArray(b.maturity_sessions) && b.maturity_sessions.length===b.horizon+1 && b.maturity_sessions[0]===b.signal_date && b.maturity_sessions.at(-1)===b.maturity_date && b.maturity_sessions.every((d,i)=>DATE.test(d) && (!i || d>b.maturity_sessions[i-1])));
      check(b.maturity_date>b.signal_date && Date.parse(b.evaluated_at)<=now && b.provenance.data_cutoff>=b.maturity_date && Date.parse(b.provenance.available_at)<=Date.parse(b.evaluated_at));
      check(DATE.test(b.provenance.data_cutoff) && b.provenance.data_cutoff<=local(b.evaluated_at).slice(0,10) && b.maturity_date<=local(b.evaluated_at).slice(0,10));
      check(b.realized_series_type==='RECONSTRUCTED_SWL2_EQUAL_WEIGHT' && b.metrics.horizon===b.horizon && b.metrics.realized.length===family.industry_codes.length);
      const realized=b.metrics.realized;
      check(new Set(realized.map(r=>r.industry_code)).size===family.model_universe_size && realized.every(r=>family.industry_codes.includes(r.industry_code) && Number.isFinite(r.realized_return) && Number.isFinite(r.scientific_target)));
      const center=mean(realized.map(r=>r.realized_return));
      check(realized.every(r=>Math.abs(r.scientific_target-(r.realized_return-center))<=1e-12));
      check(b.metrics.diagnostic_label==='NON_TRADABLE_RESEARCH_DIAGNOSTIC' && HASH.test(b.target_cross_section_hash));
      evaluated.add(id);
    }
    ids.add(e.event_id);
    previous=sha(canonicalJSON({event_id:e.event_id,body_hash:e.body_hash,previous_hash:e.previous_hash}));
  }
}

export function aggregate(evaluations,horizon) {
  const rows=evaluations.filter(e=>e.horizon===horizon).sort((a,b)=>a.signal_date.localeCompare(b.signal_date));
  const ic=rows.map(r=>r.metrics.rank_ic).filter(v=>v!==null);
  const rolling=[];
  for(let end=20;end<=rows.length;end++) {
    const block=rows.slice(end-20,end),values=block.map(r=>r.metrics.rank_ic);
    rolling.push({from:block[0].signal_date,through:block.at(-1).signal_date,rank_ic:values.includes(null)?null:mean(values),spread:mean(block.map(r=>r.metrics.top5_bottom5_spread))});
  }
  return {horizon,matured_forecast_dates:rows.length,valid_rank_ic_dates:ic.length,mean_rank_ic:mean(ic),median_rank_ic:median(ic),positive_rank_ic_fraction:mean(ic.map(v=>Number(v>0))),
    ...Object.fromEntries(['top5_mean_return','bottom5_mean_return','top5_bottom5_spread','universe_mean_return','top5_overlap_count','top5_overlap_rate','mean_absolute_rank_error','median_absolute_rank_error'].map(k=>[k,mean(rows.map(r=>r.metrics[k]))])),
    confidence_status:rows.length<20?'INSUFFICIENT_FORWARD_EVIDENCE':'DESCRIPTIVE_ONLY_OVERLAPPING_OBSERVATIONS',rolling_window_dates:20,rolling,worst_rolling_interval:rolling.length?[...rolling].sort((a,b)=>a.spread-b.spread)[0]:null};
}
export async function observe(runtimeRoot,family,now=Date.now()) {
  if(family.forward_eligible===false)return {family:{...family,forward_status:'FORWARD_INELIGIBLE',forecast_row_count:0},status:family.scientific_status,current:null,history:[],evaluations:[],metrics:[10,40,120].map(h=>aggregate([],h))};
  let forecasts=[],evaluations=[];
  if(runtimeRoot) {
    const base=await externalRoot(runtimeRoot),root=path.join(base,family.family_id);
    if(await containedExists(base,`${family.family_id}/latest.json`)) {
      const pointer=json(await read(root,'latest.json',4096));
      check(/^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$/.test(pointer.run_id) && HASH.test(pointer.manifest_sha256));
      const run=`runs/${pointer.run_id}`;
      const raw=await read(root,`${run}/manifest.json`,4096);check(sha(raw)===pointer.manifest_sha256);
      const manifest=json(raw);check(manifest.run_id===pointer.run_id && manifest.schema_version==='1.0.0' && manifest.contract==='FORWARD_INDUSTRY_FORECAST_LEDGER' && Object.keys(manifest.files).sort().join('|')==='binding.json|events.json');
      const bodies={};for(const [name,hash] of Object.entries(manifest.files)){bodies[name]=await read(root,`${run}/${name}`,16*1024*1024);check(sha(bodies[name])===hash);}
      const references=json(bodies['events.json']).events,binding=json(bodies['binding.json']);
      check(Array.isArray(references) && references.length<=10000);
      const events=[];
      for(const ref of references){
        check(Object.keys(ref).sort().join('|')==='body_hash|event_id|previous_hash' && HASH.test(ref.body_hash));
        const raw=await read(root,`objects/${ref.body_hash}.json`,512*1024);check(sha(raw)===ref.body_hash);
        events.push({...ref,body:json(raw),body_json:raw.toString()});
      }
      validateEvents(events,binding,family,now);
      const projection=e=>({...e.body,event_hash:e.body_hash,event_type:e.body.kind==='FORECAST'?'FORECAST':'EVALUATION_EVENT'});
      forecasts=events.filter(e=>e.body.kind==='FORECAST').map(projection);evaluations=events.filter(e=>e.body.kind==='EVALUATION').map(projection);
    }
  }
  return {family:{...family,forward_status:forecasts.length?'FORWARD_FORECAST':'NO_FORWARD_FORECASTS',forecast_row_count:forecasts.at(-1)?.cross_section.length??0},status:forecasts.length?'FORWARD_FORECAST':'NO_FORWARD_FORECASTS',current:forecasts.at(-1)??null,history:forecasts,evaluations,metrics:[10,40,120].map(h=>aggregate(evaluations,h))};
}

function sharedMetric(rows,codes,raw) {
  const scores=new Map(rows.map(r=>[r.industry_code,r.forecast_score]));
  const rank=values=>values.map(v=>1+values.filter(x=>x<v).length+(values.filter(x=>x===v).length-1)/2);
  const x=rank(codes.map(c=>scores.get(c))),y=rank(codes.map(c=>raw.get(c)));
  const xm=mean(x),ym=mean(y),xx=x.reduce((n,v)=>n+(v-xm)**2,0),yy=y.reduce((n,v)=>n+(v-ym)**2,0);
  const ic=xx>0&&yy>0?x.reduce((n,v,i)=>n+(v-xm)*(y[i]-ym),0)/Math.sqrt(xx*yy):null;
  const ordered=[...codes].sort((c,d)=>scores.get(d)-scores.get(c)||c.localeCompare(d));
  const actual=[...codes].sort((c,d)=>raw.get(d)-raw.get(c)||c.localeCompare(d));
  const errors=codes.map(c=>Math.abs(ordered.indexOf(c)-actual.indexOf(c)));
  const overlap=ordered.slice(0,5).filter(c=>actual.slice(0,5).includes(c)).length;
  return {rank_ic:ic,mean_absolute_rank_error:mean(errors),median_absolute_rank_error:median(errors),top5_overlap_count:overlap,top5_overlap_rate:overlap/5,top5_bottom5_spread:mean(ordered.slice(0,5).map(c=>raw.get(c)))-mean(ordered.slice(-5).map(c=>raw.get(c)))};
}
export function compare(a,b) {
  return [10,40,120].map(h=>{
    const left=new Map(a.evaluations.filter(e=>e.horizon===h).map(e=>[e.signal_date,e]));
    const right=new Map(b.evaluations.filter(e=>e.horizon===h).map(e=>[e.signal_date,e]));
    const dates=[...left.keys()].filter(d=>right.has(d)).sort(),x=[],y=[],counts={};
    for(const d of dates) {
      const aa=left.get(d),bb=right.get(d);
      check(['taxonomy_identity','target_contract','realized_series_type'].every(k=>aa[k]===bb[k]));
      const ar=new Map(aa.metrics.realized.map(r=>[r.industry_code,r.realized_return]));
      const br=new Map(bb.metrics.realized.map(r=>[r.industry_code,r.realized_return]));
      const codes=[...ar.keys()].filter(c=>br.has(c)).sort();
      check(codes.length>=10 && codes.every(c=>Math.abs(ar.get(c)-br.get(c))<=1e-12+1e-10*Math.abs(br.get(c))));
      counts[d]=codes.length;x.push(sharedMetric(aa.metrics.realized,codes,ar));y.push(sharedMetric(bb.metrics.realized,codes,ar));
    }
    const summary=rows=>{const ic=rows.map(r=>r.rank_ic).filter(v=>v!==null);return {mean_rank_ic:mean(ic),median_rank_ic:median(ic),positive_rank_ic_fraction:mean(ic.map(v=>Number(v>0))),top5_bottom5_spread:mean(rows.map(r=>r.top5_bottom5_spread)),...Object.fromEntries(['mean_absolute_rank_error','median_absolute_rank_error','top5_overlap_count','top5_overlap_rate'].map(k=>[k,mean(rows.map(r=>r[k]))]))};};
    const xx=summary(x),yy=summary(y),keys=Object.keys(xx);
    return {scope:'COMMON_FORWARD_WINDOW',metric_scope:'COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC',common_industry_counts:counts,raw_return_compatibility:dates.length?'VERIFIED':'NO_COMMON_MATURED_OBSERVATIONS',centered_target_equality_required:false,horizon:h,matured_common_dates:dates,matured_common_date_count:dates.length,
      swl2_ridge_v1:xx,swl2_ridge_v2:yy,difference_v2_minus_v1:Object.fromEntries(keys.map(k=>[k,xx[k]===null||yy[k]===null?null:yy[k]-xx[k]])),confidence_status:dates.length<20?'INSUFFICIENT_FORWARD_EVIDENCE':'DESCRIPTIVE_ONLY_OVERLAPPING_OBSERVATIONS'};
  });
}

export function createApi({runtimeRoot='',repoRoot=ROOT,origins=allowedOrigins(),now=()=>Date.now()}={}) {
  return http.createServer(async(req,res)=>{
    res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
    const reply=(status,data=null,code=null)=>{res.statusCode=status;res.end(req.method==='HEAD'?undefined:JSON.stringify({schemaVersion:'1.0.0',data,error:code?{code,message:code}:null}));};
    if(!/^(127\.0\.0\.1|localhost)(:[0-9]+)?$/.test(req.headers.host??''))return reply(403,null,'LOCAL_HOST_REQUIRED');
    if(req.headers.origin && !origins.has(req.headers.origin))return reply(403,null,'ORIGIN_NOT_ALLOWED');
    if(req.headers.origin){res.setHeader('Access-Control-Allow-Origin',req.headers.origin);res.setHeader('Vary','Origin');}
    if(!['GET','HEAD','OPTIONS'].includes(req.method))return reply(405,null,'READ_ONLY_API');
    const url=req.url??'',match=url.match(/^\/api\/industry-forecast\/(families|swl2-ridge\/compare|(?:swl2-ridge-v[12]|swl1-ridge-v[12])\/(current|history|evaluation|status))$/);
    const evidence=url.match(/^\/api\/industry-forecast\/research-evidence\/(sources|source-admissions|prospective-status|access-policy|maturity-status)$/);
    if(!match && !evidence)return reply(404,null,'INVALID_RESOURCE');
    if(req.method==='OPTIONS'){res.setHeader('Access-Control-Allow-Methods','GET, HEAD, OPTIONS');return reply(204);}
    try {
      if(evidence)return reply(200,await publicEvidence(repoRoot,evidence[1]));
      const registry=await families(repoRoot);
      if(match[1]==='families')return reply(200,await Promise.all(registry.map(async f=>(await observe(runtimeRoot,f,now())).family)));
      if(match[1]==='swl2-ridge/compare')return reply(200,compare(...await Promise.all(registry.filter(f=>f.industry_level===2).map(f=>observe(runtimeRoot,f,now())))));
      const family=registry.find(f=>f.family_id===match[1].split('/')[0].replaceAll('-','_'));check(family);
      const view=await observe(runtimeRoot,family,now());
      return reply(200,match[2]==='current'?view:match[2]==='history'?view.history:match[2]==='evaluation'?{evaluations:view.evaluations,metrics:view.metrics}:{family,status:view.status});
    }catch{return reply(503,null,'FORECAST_INTEGRITY_BLOCKER');}
  });
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const port=Number(process.env.INDUSTRY_FORECAST_API_PORT||3313);check(Number.isInteger(port)&&port>=1024&&port<=65535);
  createApi({runtimeRoot:process.env.INDUSTRY_FORECAST_RUNTIME_ROOT||''}).listen(port,'127.0.0.1',()=>process.stdout.write(`INDUSTRY_FORECAST_READ_ONLY_API 127.0.0.1:${port}\n`));
}

/** Versioned live Shadow projection from bounded, hash-verified generations. */
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {observeV2} from './v2.mjs';
import {boundedLeaf} from './bounded.mjs';

const sha=b=>createHash('sha256').update(b).digest('hex');
const requireValue=v=>{if(!v)throw new Error('V2_SHADOW_INTEGRITY_BLOCKER');};
async function read(root,name,limit=1024*1024) {
  return (await boundedLeaf(root,name,limit)).raw;
}
async function exists(root,name) {
  try {await stat(path.join(root,name));return true;} catch(error) {if(error.code==='ENOENT')return false;throw error;}
}
function verifyView(v,release) {
  requireValue(v.strategy_version==='ETF_QUANT_V2' && v.mode==='SIMULATION_ONLY'
    && v.broker_enabled===false && v.real_order_path===false && v.initial_capital==='10000'
    && v.candidate_sha256===release.candidate_sha256 && v.registry_sha256===release.registry_sha256
    && v.release_sha256===release.release_sha256 && v.scientific_status===release.scientific_status
    && v.historical_classification===release.classification && v.product_status===release.product_status
    && ['epoch_count','signal_count','intent_count','fill_count'].every(k=>Number.isSafeInteger(v[k]) && v[k]>=0)
    && Array.isArray(v.nav) && Array.isArray(v.slots) && Number.isFinite(v.cash_weight) && v.cash_weight>=0 && v.cash_weight<=1);
  requireValue(typeof v.started==='boolean' && typeof v.armed==='boolean'
    && /^[0-9]+(?:\.[0-9]+)?$/.test(v.cash) && Number(v.cash)>=0
    && /^[0-9]+(?:\.[0-9]+)?$/.test(v.balance) && Number(v.balance)>0
    && (v.started || [v.epoch_count,v.signal_count,v.intent_count,v.fill_count,v.nav.length].every(n=>n===0)));
  return v;
}
export async function observeV2Current({repoRoot,runtimeRoot='',controlRoot=''}={}) {
  const research=await observeV2(repoRoot),release=research.release;
  let transportWait=null;
  let view={strategy_version:'ETF_QUANT_V2',mode:'SIMULATION_ONLY',scientific_status:release.scientific_status,
    historical_classification:release.classification,product_status:release.product_status,candidate_sha256:release.candidate_sha256,
    registry_sha256:release.registry_sha256,release_sha256:release.release_sha256,initial_capital:'10000',armed:false,started:false,
    waiting_reason:'NOT_ARMED',epoch_count:0,signal_count:0,intent_count:0,fill_count:0,signal_date:null,top5:[],slots:[],
    cash_weight:1,next_accounting_state:'NOT_STARTED',execution_date:null,balance:'10000',cash:'10000',holdings:[],nav:[],
    benchmark:{identity:'CSI_300',points:[]},turnover:null,latest_data_date:null,latest_data_time:null,broker_enabled:false,real_order_path:false};
  if(controlRoot && await exists(controlRoot,'latest_observation.json')) {
    const control=JSON.parse(await read(controlRoot,'latest_observation.json'));
    requireValue(control.strategy_version==='ETF_QUANT_V2');
    if(control.view) view=verifyView(control.view,release);
    else {
      // Source waits have transport metadata, while the account remains empty.
      requireValue(typeof control.status==='string' && /^[A-Z0-9_]+$/.test(control.status)
        && typeof control.shadow_runtime_armed==='boolean'
        && (!control.data_cutoff || /^\d{4}-\d{2}-\d{2}$/.test(control.data_cutoff))
        && (!control.reason_code || /^[A-Z0-9_]+$/.test(control.reason_code)));
      view={...view,armed:control.shadow_runtime_armed,waiting_reason:control.reason_code??control.status,
        latest_data_date:control.data_cutoff??null};
      transportWait=control;
    }
  }
  if(runtimeRoot && await exists(runtimeRoot,'latest.json')) {
    const pointer=JSON.parse(await read(runtimeRoot,'latest.json',4096));
    requireValue(/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(pointer.run_id) && /^[a-f0-9]{64}$/.test(pointer.manifest_sha256));
    const manifestBytes=await read(runtimeRoot,`runs/${pointer.run_id}/manifest.json`,65536),manifest=JSON.parse(manifestBytes);
    requireValue(sha(manifestBytes)===pointer.manifest_sha256 && manifest.run_id===pointer.run_id
      && manifest.strategy_version==='ETF_QUANT_V2' && manifest.release_sha256===release.release_sha256);
    requireValue(Object.keys(manifest.files).sort().join(',')==='state.json,view.json');
    for(const name of Object.keys(manifest.files)) {
      const bytes=await read(runtimeRoot,`runs/${pointer.run_id}/${name}`,4*1024*1024);
      requireValue(sha(bytes)===manifest.files[name]);
    }
    const bytes=await read(runtimeRoot,`runs/${pointer.run_id}/view.json`,4*1024*1024);
    view=verifyView(JSON.parse(bytes),release);
    if(transportWait && Number.isFinite(Date.parse(transportWait.observed_at))
      && Date.parse(transportWait.observed_at)>Date.parse(manifest.created_at)) {
      // Keep the verified account/NAV; only a newer transport wait can update health.
      view={...view,armed:transportWait.shadow_runtime_armed,
        waiting_reason:transportWait.reason_code??transportWait.status};
    }
  }
  return {...view,final_oos:research.final_oos,mapping_summary:research.mapping,
    mapping_inventory:research.mapping_inventory,candidate_etfs:research.registry_entries.filter(r=>view.top5.some(t=>t[0]===r.industry_code)),
    simulation_costs:{commission_bps:3,slippage_bps_per_side:5,stamp_duty_bps:0,minimum_commission:'0',lot_size:100}};
}

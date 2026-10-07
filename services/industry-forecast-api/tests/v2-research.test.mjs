import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createApi,families,observe,validateV2} from '../server.mjs';

async function fixture() {
  const f=JSON.parse(await readFile(new URL('../../../config/research/swl1-ridge-v2-family.json',import.meta.url)));
  const artifacts={};
  for(const [key,ref] of Object.entries(f).filter(([key])=>key.endsWith('_reference')))artifacts[key]=JSON.parse(await readFile(new URL(`../../../${ref.path}`,import.meta.url)));
  return {f,artifacts};
}

for(const state of ['FAILED_VALIDATION','AWAITING_PROSPECTIVE_FINAL_OOS','NO_DEVELOPMENT_CANDIDATE','VALIDATION_INTERVAL_NOT_UNSEEN','NOT_RESEARCHABLE_WITH_CURRENT_DATA'])test(`${state} stays inactive and has coherent lineage`,async()=>{
  const {f,artifacts:a}=await fixture(),s=a.status_reference;
  f.scientific_status=s.scientific_status=state;
  if(state==='AWAITING_PROSPECTIVE_FINAL_OOS')s.validation_passed=a.validation_reference.passed=true;
  else if(state!=='FAILED_VALIDATION') {
    Object.assign(s,{candidate_hash:null,validation_opened:false,validation_passed:null});f.model_contract_hash=f.protocol_reference.sha256;
    for(const key of ['candidate_reference','validation_reference']){delete f[key];delete a[key];}
    for(const row of a.development_reference.leaderboard)row.admitted=false;
  }
  validateV2(f,a);
  const view=await observe('/unreadable/must-not-read',f);
  assert.equal(view.current,null);assert.deepEqual(view.history,[]);assert.deepEqual(view.evaluations,[]);assert.equal(view.metrics[0].mean_rank_ic,null);
  f.forward_eligible=true;assert.throws(()=>validateV2(f,a));
});

for(const mutation of ['candidate','anchor','reopen','oos'])test(`V2 rejects ${mutation} tampering`,async()=>{
  const {f,artifacts:a}=await fixture();
  if(mutation==='candidate')a.validation_reference.lineage.candidate_hash='f'.repeat(64);
  else if(mutation==='anchor')a.status_reference.public_preregistration_anchor.external_merge_witness.exact_remote_bytes_verified=false;
  else if(mutation==='reopen')a.status_reference.validation_reopened=true;
  else a.status_reference.final_oos_opened=true;
  assert.throws(()=>validateV2(f,a));
});

test('public V2 metadata and all read-only routes expose closure without runtime access',async t=>{
  const f=(await families()).find(f=>f.family_id==='swl1_ridge_v2');
  assert.equal(f.generation,2);assert.equal(f.industry_level,1);assert.equal(f.model_universe_size,30);assert.equal(f.research_status,'FAILED_VALIDATION');
  assert.equal(f.validation_status,'FAIL');assert.equal(f.final_oos_status,'PROSPECTIVE_NOT_OPENED');assert.equal(f.membership_confidence,'RECONSTRUCTED');assert.equal(f.primary_series,'RECONSTRUCTED_SWL1_EQUAL_WEIGHT');assert.equal(f.protocol_hash.length,64);assert.equal(f.candidate_hash.length,64);
  assert.equal(f.research_evidence.development.leaderboard.length,16);assert.equal(f.research_evidence.validation.metrics.signal_count,126);
  const server=createApi({runtimeRoot:'/unreadable/must-not-read'});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
  const base=`http://127.0.0.1:${server.address().port}/api/industry-forecast/swl1-ridge-v2`;
  for(const route of ['current','history','evaluation','status']) {
    const response=await fetch(`${base}/${route}`);assert.equal(response.status,200);
    const {data}=await response.json();
    if(route==='current'){assert.equal(data.current,null);assert.equal(data.family.forward_eligible,false);}
    if(route==='history')assert.deepEqual(data,[]);
    if(route==='evaluation')assert.equal(data.metrics[0].mean_rank_ic,null);
    if(route==='status')assert.equal(data.status,'FAILED_VALIDATION');
  }
});

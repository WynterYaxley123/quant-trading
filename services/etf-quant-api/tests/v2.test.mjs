import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {once} from 'node:events';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {observeV2} from '../v2.mjs';
import {createApi} from '../server.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
test('V2 aggregates bind frozen candidate, failed original Validation and single Final OOS',async()=>{
  const v=await observeV2(root);
  assert.equal(v.product,'ETF_QUANT_V2');assert.equal(v.specification.alpha,30);
  assert.equal(v.validation_status,'FAILED');assert.equal(v.revision_independently_validated,false);
  assert.equal(v.final_oos_opened,true);assert.equal(v.epoch_count,0);
  assert.equal(v.final_oos.open_count,1);assert.equal(v.final_oos.model_retuned,false);
  assert.equal(v.scientific_status,'PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE');
  assert.equal(v.membership_tier_rows.A,0);assert.equal(v.broker_enabled,false);
});
test('V2 endpoint keeps local origin/read-only/path boundaries',async t=>{
  const server=createApi({repoRoot:root});server.listen(0,'127.0.0.1');await once(server,'listening');t.after(()=>server.close());
  const base=`http://127.0.0.1:${server.address().port}/api/etf-quant/v2/research`;
  assert.equal((await fetch(base)).status,200);
  assert.equal((await fetch(base,{method:'POST'})).status,405);
  assert.equal((await fetch(base,{headers:{Origin:'https://external.invalid'}})).status,403);
  assert.equal((await fetch(base+'?path=final-oos')).status,400);
  assert.equal((await fetch(base+'/other')).status,400);
});
test('forged report or tampered certified fit source fails closed',async t=>{
  const temp=await mkdtemp(path.join(os.tmpdir(),'SYNTHETIC-v2-integrity-'));t.after(()=>rm(temp,{recursive:true,force:true}));
  const manifest=JSON.parse(await readFile(path.join(root,'reports/engineering/shadow-task-installation-integrity.json')));
  const delta=JSON.parse(await readFile(path.join(root,'reports/engineering/v7-integrity.json')));
  const names=new Set([...Object.keys(manifest.implementation_integrity.files),...Object.keys(delta.implementation_integrity.files),'reports/engineering/shadow-task-installation-integrity.json','reports/engineering/v7-integrity.json']);
  for(const name of names){await mkdir(path.dirname(path.join(temp,name)),{recursive:true});await writeFile(path.join(temp,name),await readFile(path.join(root,name)));}
  assert.equal((await observeV2(temp)).validation_status,'FAILED');
  await writeFile(path.join(temp,'research/etf_quant_v2/experiment.py'),'SYNTHETIC tamper');
  await assert.rejects(observeV2(temp));
});

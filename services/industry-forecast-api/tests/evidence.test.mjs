import {test} from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createApi} from '../server.mjs';
import {publicEvidence} from '../evidence.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
test('six evidence resources preserve blocked scientific readiness and zero real facts',async()=>{
  for(const resource of ['sources','source-admissions','prospective-status','access-policy','maturity-status','source-qualification']) {
    const data=await publicEvidence(root,resource);assert.equal(data.schema_version,1);
    const raw=JSON.stringify(data);assert.ok(raw.length<64*1024);assert.doesNotMatch(raw,/(?:D:\\|password|api_key|raw_prices|raw_membership)/);
  }
  const status=await publicEvidence(root,'prospective-status');
  const inventory=await publicEvidence(root,'sources');
  assert.equal(inventory.sources.find(s=>s.source_id==='sina-corporate-actions').schema_version,2);
  assert.equal(inventory.sources.find(s=>s.source_id==='tdx-daily-bars').industry_level,null);
  assert.equal(inventory.sources.find(s=>s.source_id==='official-swl1-index').taxonomy_version,null);
  assert.equal(status.future_protocol,'NOT_CREATED');assert.equal(status.historical_numeric_access_isolation,'NOT_CERTIFIED');
  assert.equal(status.next_generation_research_readiness,'DATA_SOURCE_NOT_READY');assert.equal(status.formal_observations,0);
  assert.ok(status.maturity.every(m=>m.status==='PENDING_MATURITY' && m.matured_observations===0));
  const qualification=await publicEvidence(root,'source-qualification');
  assert.equal(qualification.current_sources_audited,12);assert.equal(qualification.official_documents_verified,15);
  assert.equal(qualification.real_sources_admitted,0);assert.equal(qualification.research_readiness,'DATA_SOURCE_NOT_READY');
  assert.equal(qualification.owner_actions.length,5);assert.equal(qualification.numeric_qa_run,false);
  assert.ok(qualification.sources.some(s=>s.source_id==='tdx-corporate-actions' && s.kind==='CORPORATE_ACTIONS'));
});
test('read-only exact routes reject writes, traversal, query and untrusted origin',async()=>{
  const server=createApi({runtimeRoot:'this-must-never-be-opened'});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}/api/industry-forecast/research-evidence/`;
  try {
    assert.equal((await fetch(base+'prospective-status')).status,200);
    assert.equal((await fetch(base+'source-qualification')).status,200);
    assert.equal((await fetch(base+'source-qualification',{method:'POST'})).status,405);
    assert.equal((await fetch(base+'prospective-status',{method:'POST'})).status,405);
    assert.equal((await fetch(base+'prospective-status?path=mother')).status,404);
    assert.equal((await fetch(base+'%2e%2e%2fmothers')).status,404);
    assert.equal((await fetch(base+'prospective-status',{headers:{origin:'https://evil.invalid'}})).status,403);
    const head=await fetch(base+'maturity-status',{method:'HEAD'});assert.equal(head.status,200);assert.equal(await head.text(),'');
  } finally {await new Promise(resolve=>server.close(resolve));}
});

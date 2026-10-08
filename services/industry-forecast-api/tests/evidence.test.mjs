import {test} from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createApi} from '../server.mjs';
import {publicEvidence} from '../evidence.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
test('five evidence resources preserve blocked scientific readiness and zero real facts',async()=>{
  for(const resource of ['sources','source-admissions','prospective-status','access-policy','maturity-status']) {
    const data=await publicEvidence(root,resource);assert.equal(data.schema_version,1);
    const raw=JSON.stringify(data);assert.ok(raw.length<64*1024);assert.doesNotMatch(raw,/(?:D:\\|password|api_key|raw_prices|raw_membership)/);
  }
  const status=await publicEvidence(root,'prospective-status');
  assert.equal(status.future_protocol,'NOT_CREATED');assert.equal(status.historical_numeric_access_isolation,'NOT_CERTIFIED');
  assert.equal(status.next_generation_research_readiness,'DATA_SOURCE_NOT_READY');assert.equal(status.formal_observations,0);
  assert.ok(status.maturity.every(m=>m.status==='PENDING_MATURITY' && m.matured_observations===0));
});
test('read-only exact routes reject writes, traversal, query and untrusted origin',async()=>{
  const server=createApi({runtimeRoot:'this-must-never-be-opened'});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}/api/industry-forecast/research-evidence/`;
  try {
    assert.equal((await fetch(base+'prospective-status')).status,200);
    assert.equal((await fetch(base+'prospective-status',{method:'POST'})).status,405);
    assert.equal((await fetch(base+'prospective-status?path=mother')).status,404);
    assert.equal((await fetch(base+'%2e%2e%2fmothers')).status,404);
    assert.equal((await fetch(base+'prospective-status',{headers:{origin:'https://evil.invalid'}})).status,403);
    const head=await fetch(base+'maturity-status',{method:'HEAD'});assert.equal(head.status,200);assert.equal(await head.text(),'');
  } finally {await new Promise(resolve=>server.close(resolve));}
});

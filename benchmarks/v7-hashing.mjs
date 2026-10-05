/** Synthetic engineering I/O profile; all certified bytes are fully verified. */
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {boundedLeaf} from '../services/etf-quant-api/bounded.mjs';

const root=process.cwd(),sha=b=>createHash('sha256').update(b).digest('hex');
const parent=JSON.parse(await readFile('reports/engineering/shadow-task-installation-integrity.json')).implementation_integrity;
const delta=JSON.parse(await readFile('reports/engineering/v7-integrity.json')).implementation_integrity;
const entries=Object.entries({...parent.files,...delta.files});
async function run(concurrency) {
  const result={};const start=performance.now();
  for(let i=0;i<entries.length;i+=concurrency)await Promise.all(entries.slice(i,i+concurrency).map(async([name,expected])=>{
    const actual=sha((await boundedLeaf(root,name,512*1024)).raw);
    if(actual!==expected)throw new Error('PROFILE_SOURCE_INTEGRITY_BLOCKER');
    result[name]=actual;
  }));
  const ordered=Object.fromEntries(Object.entries(result).sort(([a],[b])=>a.localeCompare(b)));
  return {seconds:(performance.now()-start)/1000,digest:sha(JSON.stringify(ordered))};
}
const before=await run(1),after=await run(8);
if(before.digest!==after.digest)throw new Error('PROFILE_EQUIVALENCE_BLOCKER');
await writeFile('/tmp/v7-js-profile.json',JSON.stringify({certified_files:entries.length,before,after,
  exact_hash_equivalence:true,full_verification:true,timing_is_not_a_gate:true},null,2)+'\n');

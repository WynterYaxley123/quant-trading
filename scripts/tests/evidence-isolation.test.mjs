import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,symlinkSync,rmSync,realpathSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {checkedDirectory,verifyContainer} from '../engineering/prospective-isolation.mjs';

const valid=()=>({Config:{User:'65534:65534'},HostConfig:{ReadonlyRootfs:true,NetworkMode:'none',Privileged:false,PidMode:'',CapDrop:['ALL'],SecurityOpt:['no-new-privileges'],Devices:[],VolumesFrom:null},Mounts:[{Type:'bind',RW:false,Destination:'/view'},{Type:'bind',RW:false,Destination:'/policy'}]});
test('closed worker mount/OS policy rejects unexpected privileges and volumes',()=>{
  assert.equal(verifyContainer(valid()),true);
  for(const mutate of [c=>c.Mounts.push({Type:'bind',RW:false,Destination:'/mother'}),c=>c.Mounts[0].RW=true,c=>c.HostConfig.NetworkMode='host',c=>c.HostConfig.Privileged=true,c=>c.Config.User='0',c=>c.HostConfig.ReadonlyRootfs=false,c=>c.HostConfig.VolumesFrom=['mother']]) {
    const c=valid();mutate(c);assert.throws(()=>verifyContainer(c),/PROCESS_ISOLATION_DENIED/);
  }
});
test('actual filesystem symlink or Windows junction cannot enter a mount',()=>{
  const root=mkdtempSync(path.join(tmpdir(),'synthetic-evidence-path-'));
  try {
    const target=path.join(root,'target'),link=path.join(root,'link');mkdirSync(target);
    symlinkSync(target,link,process.platform==='win32'?'junction':'dir');
    assert.throws(()=>checkedDirectory(link),/PROCESS_ISOLATION_DENIED/);
    for(const bad of ['../target','C:relative',target+',target=/mother',target+'\n'])assert.throws(()=>checkedDirectory(bad));
    assert.equal(checkedDirectory(target),realpathSync.native(target));
    if(process.platform==='win32')assert.equal(checkedDirectory(target.toUpperCase()),realpathSync.native(target));
  } finally {rmSync(root,{recursive:true,force:true});}
});

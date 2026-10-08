/** Task-owned Docker containment acceptance. Never mounts real lake/runtime data. */
import {execFileSync} from 'node:child_process';
import {lstatSync, realpathSync, readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const check=v=>{if(!v)throw new Error('PROCESS_ISOLATION_DENIED');};
export function checkedDirectory(value) {
  check(typeof value==='string' && path.isAbsolute(value) && !value.includes(',') && !value.includes('\n'));
  // Windows temp roots may use 8.3 aliases or different letter casing. Reject
  // links on the original path BEFORE resolving legitimate filesystem aliases.
  if(process.platform==='win32')check(/^[A-Za-z]:[\\/]/.test(value));
  const lexical=path.resolve(value);
  for(let p=lexical;;p=path.dirname(p)) {check(!lstatSync(p).isSymbolicLink());if(path.dirname(p)===p)break;}
  const resolved=realpathSync.native(lexical);
  for(let p=resolved;;p=path.dirname(p)) {check(!lstatSync(p).isSymbolicLink());if(path.dirname(p)===p)break;}
  return resolved;
}
export function verifyContainer(c) {
  check(c.Config.User==='65534:65534' && c.HostConfig.ReadonlyRootfs===true);
  check(c.HostConfig.NetworkMode==='none' && c.HostConfig.Privileged===false && c.HostConfig.PidMode==='');
  check(c.HostConfig.CapDrop?.includes('ALL') && c.HostConfig.SecurityOpt?.some(s=>s.startsWith('no-new-privileges')));
  check(c.Mounts.length===2 && c.Mounts.every(m=>m.Type==='bind' && m.RW===false));
  check(c.Mounts.map(m=>m.Destination).sort().join('|')==='/policy|/view');
  check(c.HostConfig.Devices.length===0 && !c.HostConfig.VolumesFrom?.length);
  return true;
}
export function run({repo, output, image='quant-trading-dev:ci'}) {
  repo=checkedDirectory(repo);output=checkedDirectory(output);
  check(/^[a-zA-Z0-9_./:-]+$/.test(image));
  const docker=args=>execFileSync('docker',args,{encoding:'utf8',maxBuffer:4*1024*1024,stdio:['ignore','pipe','pipe']});
  const workerImage=`prospective-evidence-worker:${process.pid}`;
  docker(['build','--build-arg',`DEV_IMAGE=${image}`,'-f',path.join(repo,'research/evidence/Dockerfile.worker'),'-t',workerImage,repo]);
  const results=[];
  try {
    for(const poison of ['positive','negative','nan']) {
      const bundle=path.join(output,`bundle-${poison}`);check(!readExists(bundle));
      docker(['run','--rm','--network','none','--mount',`type=bind,source=${repo},target=/workspace,readonly`,'--mount',`type=bind,source=${output},target=/delivery`,image,'python','-m','examples.prospective_evidence_demo.isolation_bundle','--output',`/delivery/bundle-${poison}`,'--poison',poison]);
      const view=checkedDirectory(path.join(bundle,'views/view')),policy=checkedDirectory(path.join(bundle,'policy'));
      const pin=JSON.parse(readFileSync(path.join(bundle,'launch.json'),'utf8')).pin;
      const id=docker(['create','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','512m','--cpus','1','--user','65534:65534','--mount',`type=bind,source=${view},target=/view,readonly`,'--mount',`type=bind,source=${policy},target=/policy,readonly`,workerImage,'--pin',pin]).trim();
      try {
        const inspected=JSON.parse(docker(['inspect',id]))[0];verifyContainer(inspected);
        const result=JSON.parse(docker(['start','-a',id]));
        check(result.process_isolation==='PASS_LINUX_DOCKER_SYNTHETIC' && result.direct_mother_read==='DENIED' && result.network==='DENIED');
        results.push(result);
      } finally {docker(['rm','-f',id]);}
    }
    check(new Set(results.map(r=>r.content_hash)).size===1 && new Set(results.map(r=>r.derived_hash)).size===1);
    const receipt={scope:'SYNTHETIC_ONLY',logical_boundary:'PASS',physical_view_boundary:'PASS',process_isolation:'PASS_LINUX_DOCKER_SYNTHETIC',windows_native_process_isolation:'NOT_ESTABLISHED',future_poison_variants:results.length,worker_mounts:['/view:readonly','/policy:readonly'],results};
    writeFileSync(path.join(output,'isolation-acceptance.json'),JSON.stringify(receipt,null,2)+'\n');
    return receipt;
  } finally {docker(['image','rm',workerImage]);}
}
function readExists(p){try{lstatSync(p);return true;}catch(e){if(e.code==='ENOENT')return false;throw e;}}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const [repo,output,image]=process.argv.slice(2);if(!readExists(output))mkdirSync(output,{recursive:true});
  console.log(JSON.stringify(run({repo,output,image})));
}

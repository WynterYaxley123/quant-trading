/** Bind the existing dashboard build to its exact current source; never include a private preview. */
import {readdir,readFile,writeFile,realpath} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
async function inventory(root,prefix='') {
  const result={};
  for(const entry of await readdir(path.join(root,prefix),{withFileTypes:true})) {
    const name=path.posix.join(prefix,entry.name);
    if(entry.isSymbolicLink())throw new Error('BUNDLE_LINK_DENIED');
    if(entry.isDirectory())Object.assign(result,await inventory(root,name));
    else if(entry.isFile()&&entry.name!=='bundle-manifest.json')result[name]=sha(await readFile(path.join(root,name)));
  }
  return result;
}
const [repoRoot,bundleRoot]=process.argv.slice(2);
if(!repoRoot||!bundleRoot||!path.isAbsolute(repoRoot)||!path.isAbsolute(bundleRoot)||await realpath(bundleRoot)!==path.resolve(bundleRoot))throw new Error('EXPLICIT_BUNDLE_ROOT_REQUIRED');
const source=await inventory(path.join(repoRoot,'dashboard/src'));
const source_sha256=Object.fromEntries(Object.entries(source).map(([name,hash])=>['dashboard/src/'+name,hash]));
for(const name of ['dashboard/package.json','dashboard/pnpm-lock.yaml','dashboard/index.html','dashboard/vite.config.ts'])source_sha256[name]=sha(await readFile(path.join(repoRoot,name)));
const result={schema_version:1,service:'REV10_DASHBOARD_BUNDLE',model_hash:sha(await readFile(path.join(repoRoot,'config/research/swl1-rev10-short-v1.json'))),source_sha256,files:await inventory(bundleRoot)};
await writeFile(path.join(bundleRoot,'bundle-manifest.json'),JSON.stringify(result,null,2)+'\n');
process.stdout.write(JSON.stringify({status:'REV10_BUNDLE_BOUND',files:Object.keys(result.files).length})+'\n');

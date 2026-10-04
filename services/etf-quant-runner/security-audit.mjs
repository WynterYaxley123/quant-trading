/** Read-only Git publication audit; outputs identifiers/counts, NEVER values. */
import {spawnSync} from 'node:child_process';
import {readFileSync,realpathSync,lstatSync,statSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
// Recursive key order matches Python's Unicode code-point ordering. Arrays retain order.
export function canonicalJSON(value) {
  if(Array.isArray(value))return '['+value.map(canonicalJSON).join(',')+']';
  if(value!==null && typeof value==='object') {
    const compare=(a,b)=>{
      const x=Array.from(a,c=>c.codePointAt(0)),y=Array.from(b,c=>c.codePointAt(0));
      for(let i=0;i<Math.min(x.length,y.length);i++)if(x[i]!==y[i])return x[i]-y[i];
      return x.length-y.length;
    };
    return '{'+Object.keys(value).sort(compare).map(key=>JSON.stringify(key)+':'+canonicalJSON(value[key])).join(',')+'}';
  }
  return JSON.stringify(value);
}
export function certificateHash(integrity) {
  return createHash('sha256').update(canonicalJSON(Object.fromEntries(
    Object.entries(integrity).filter(([key])=>key!=='certificate_sha256')
  ))).digest('hex');
}
export function repositoryFile(root,name) {
  const blocked=()=>{throw new Error('REPOSITORY_PATH_BLOCKER');};
  if(typeof name!=='string' || !name || name.includes('\0') || name.includes('\\')
    || path.isAbsolute(name) || path.win32.parse(name).root
    || name.split('/').some(part=>!part || part==='.' || part==='..'))blocked();
  const realRoot=realpathSync(root),candidate=path.resolve(realRoot,name);
  const contained=target=>{
    const relative=path.relative(realRoot,target);
    return relative!=='' && relative!=='..' && !relative.startsWith('..'+path.sep) && !path.isAbsolute(relative);
  };
  if(!contained(candidate))blocked();
  const resolved=realpathSync(candidate);
  if(!contained(resolved) || !statSync(resolved).isFile())blocked();
  return resolved;
}
export function verifyCurrentCertificate(current,parent,parentBytes,parentPath='reports/engineering/v4-integrity.json') {
  if(current.identifier!=='CURRENT_IMPLEMENTATION_INTEGRITY'
    || current.canonicalization!=='JSON_SORTED_KEYS_COMPACT_UTF8_V1'
    || current.parent_manifest_path!==parentPath
    || current.parent_manifest_sha256!==createHash('sha256').update(parentBytes).digest('hex')
    || ['previous_certificate_sha256','previous_transition_sha256','previous_source_hashes','candidate_sha256']
      .some(key=>canonicalJSON(current[key])!==canonicalJSON(parent[key]))
    || Object.keys(parent.files).some(name=>!Object.hasOwn(current.files,name))
    || Object.entries(parent.files).some(([name,before])=>before!==current.files[name] && !current.changes.some(change=>
      change.path===name && change.before_sha256===before && change.after_sha256===current.files[name]))
    || current.certificate_sha256!==certificateHash(current))throw new Error('CERTIFICATE_TRANSITION_BLOCKER');
}
function git(args,input,encoding='utf8') {
  const r=spawnSync('git',['--no-optional-locks',...args],{cwd:repo,input,encoding,maxBuffer:512*1024*1024});
  if(r.status!==0) throw new Error('READ_ONLY_AUDIT_COMMAND_BLOCKED');
  return r.stdout;
}
export function secretKinds(text) {
  const kinds=[];
  if(/-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/.test(text)) kinds.push('PRIVATE_KEY');
  if(/\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b/.test(text)) kinds.push('GITHUB_TOKEN');
  if(/\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{35,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b/.test(text)) kinds.push('API_TOKEN');
  for(const line of text.split(/\r?\n/)) {
    const match=line.match(/(?:password|api[_-]?key|api[_-]?token|app[_-]?secret|access[_-]?token)\s*[=:]\s*["']?([^"'\s,;]{16,})/i);
    // Human-reviewed exact legacy README dummy argon2 template (xxxx/yyyy).
    // An altered line or a real hash is NOT exempted by this fingerprint.
    const reviewedDummy=createHash('sha256').update(line).digest('hex')==='2077e82fcc7bfbccf7eb0f671d597addc90ff9221fae04edef07a81d1178dd2a';
    if(match && !reviewedDummy && !/(?:synthetic|example|placeholder|\$\{|process\.env|os\.getenv|os\.environ|REDACTED|^<)/i.test(match[1])) kinds.push('CREDENTIAL_ASSIGNMENT');
    if(/https?:\/\/[^\s/@:]+:[^\s/@]+@/.test(line) && !/(?:example|synthetic|invalid|placeholder|<|\$\{)/i.test(line)) kinds.push('EMBEDDED_URL_CREDENTIAL');
  }
  return [...new Set(kinds)];
}
const forbiddenData = name=> /^(?:data|runtime|external|lake|exports|cache|logs|secrets)\//.test(name)
  || /(?:^|\/)\.env(?:$|\.(?!example$))/.test(name)
  || /\.(?:db|sqlite3?|h5|hdf5|parquet|p12|pfx)$/.test(name)
  || /(?:^|\/)node_modules\//.test(name)
  || (/^reports\/(backtests|research)\//.test(name) && !name.endsWith('/.gitkeep'));
const sealedPerformance = name=>/(?:validation|final[_-]?oos)/i.test(name)
  && /(?:performance|predictions|results|returns|metrics)\.(json|csv|parquet)$/i.test(name);

export function audit() {
  const tracked=git(['ls-files','-z']).split('\0').filter(Boolean);
  const extra=git(['ls-files','--others','--exclude-standard','-z']).split('\0').filter(Boolean);
  const candidates=[],large=[],forbidden=[],sealed=[];
  for(const [scope,names] of [['tracked',tracked],['new',extra]]) for(const name of names) {
    if(forbiddenData(name))forbidden.push({scope,path:name});
    if(sealedPerformance(name)){sealed.push({scope,path:name});continue;} // Do NOT inspect sealed content.
    const target=path.join(repo,name), info=lstatSync(target);
    if(info.isSymbolicLink() || !realpathSync(target).startsWith(repo+path.sep)) {
      forbidden.push({scope,path:name,kind:'LINK_OR_CONTAINMENT'});continue;
    }
    if(info.size>500*1024)large.push({scope,path:name,bytes:info.size});
    const kinds=secretKinds(readFileSync(target,'utf8'));
    if(kinds.length)candidates.push({scope,path:name,kinds});
  }
  const objects=git(['rev-list','--objects','--all']).trim().split('\n').filter(Boolean)
    .map(line=>({id:line.slice(0,40),name:line.slice(41)}));
  const unsafe=objects.filter(o=>o.name && sealedPerformance(o.name));
  sealed.push(...unsafe.map(o=>({scope:'history',path:o.name,blob:o.id})));
  const scan=objects.filter(o=>!unsafe.some(p=>p.id===o.id));
  const checks=git(['cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],scan.map(o=>o.id).join('\n')+'\n')
    .trim().split('\n').map(line=>line.split(' '));
  const names=new Map(objects.map(o=>[o.id,o.name]));
  const blobs=checks.filter(([,type])=>type==='blob');
  for(const [id,,size] of blobs) {
    const name=names.get(id)||'';
    if(forbiddenData(name))forbidden.push({scope:'history',path:name,blob:id});
    if(Number(size)>500*1024)large.push({scope:'history',path:name,blob:id,bytes:Number(size)});
  }
  const content=blobs.length?git(['cat-file','--batch'],blobs.map(([id])=>id).join('\n')+'\n',null):Buffer.alloc(0);
  let offset=0;
  for(const [id,,expectedSize] of blobs) {
    const end=content.indexOf(10,offset),header=content.subarray(offset,end).toString('utf8').split(' ');
    if(header[0]!==id || Number(header[2])!==Number(expectedSize))throw new Error('HISTORY_STREAM_BLOCKER');
    offset=end+1;const size=Number(expectedSize),body=content.subarray(offset,offset+size).toString('utf8');offset+=size+1;
    const kinds=secretKinds(body);
    if(kinds.length)candidates.push({scope:'history',path:names.get(id)||'',blob:id,kinds});
  }
  const url=git(['config','--get','remote.origin.url']).trim();
  let remote;
  try {const u=new URL(url);remote={name:'origin',scheme:u.protocol,host:u.hostname,path:u.pathname,embedded_credentials:!!(u.username||u.password)};}
  catch {remote={name:'origin',scheme:'OTHER',embedded_credentials:/:[^/@\s]+@/.test(url)};}
  // The historical firewall prohibited all infrastructure edits. Public engineering
  // now permits a current transition with immutable V1/V2/V3/V4 provenance.
  const previousBytes=readFileSync(repositoryFile(repo,'reports/etf_quant/autonomous_code_integrity_v1.json'));
  const previous=JSON.parse(previousBytes);
  const parentBytes=readFileSync(repositoryFile(repo,'reports/engineering/repository-health.json'));
  const parent=JSON.parse(parentBytes).implementation_integrity;
  const v4Bytes=readFileSync(repositoryFile(repo,'reports/engineering/v4-integrity.json'));
  const integrity=JSON.parse(v4Bytes).implementation_integrity;
  const canonicalParent=Object.fromEntries(Object.keys(parent.files).sort().map(name=>[name,parent.files[name]]));
  const previousTransition=readFileSync(repositoryFile(repo,'docs/archive/engineering/public_repo_adversarial_remediation_v2.json'));
  const canonicalHashes=Object.fromEntries(Object.keys(integrity.files).sort().map(name=>[name,integrity.files[name]]));
  if(integrity.identifier!=='PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V4'
    || parent.identifier!=='PUBLIC_REPO_IMPLEMENTATION_INTEGRITY_V3'
    || integrity.parent_manifest_sha256!==createHash('sha256').update(parentBytes).digest('hex')
    || parent.certificate_sha256!==createHash('sha256').update(JSON.stringify(canonicalParent)).digest('hex')
    || ['previous_certificate_sha256','previous_transition_sha256','candidate_sha256'].some(key=>integrity[key]!==parent[key])
    || canonicalJSON(integrity.previous_source_hashes)!==canonicalJSON(parent.previous_source_hashes)
    || Object.keys(parent.files).some(name=>!Object.hasOwn(integrity.files,name))
    || Object.entries(parent.files).some(([name,before])=>before!==integrity.files[name] && !integrity.changes.some(change=>
      change.path===name && change.before_sha256===before && change.after_sha256===integrity.files[name]))
    || integrity.previous_transition_sha256!==createHash('sha256').update(previousTransition).digest('hex')
    || integrity.certificate_sha256!==createHash('sha256').update(JSON.stringify(canonicalHashes)).digest('hex')
    || integrity.previous_certificate_sha256!==createHash('sha256').update(previousBytes).digest('hex')
    || Object.keys(integrity.previous_source_hashes).length!==Object.keys(previous.files).length
    || Object.entries(previous.files).some(([name,hash])=>integrity.previous_source_hashes[name]!==hash)
    || integrity.candidate_sha256!==previous.candidate_sha256
    || Object.keys(previous.files).some(name=>!Object.hasOwn(integrity.files,name))) throw new Error('CERTIFICATE_TRANSITION_BLOCKER');
  const previousCurrentPath='reports/engineering/current-implementation-integrity.json';
  const previousCurrentBytes=readFileSync(repositoryFile(repo,previousCurrentPath));
  const previousCurrent=JSON.parse(previousCurrentBytes).implementation_integrity;
  verifyCurrentCertificate(previousCurrent,integrity,v4Bytes);
  const hotfixPath='reports/engineering/release-hotfix-integrity.json';
  const hotfixBytes=readFileSync(repositoryFile(repo,hotfixPath));
  const hotfix=JSON.parse(hotfixBytes).implementation_integrity;
  verifyCurrentCertificate(hotfix,previousCurrent,previousCurrentBytes,previousCurrentPath);
  const prerequisitePath='reports/engineering/etf-quant-v2-integrity.json';
  const prerequisiteBytes=readFileSync(repositoryFile(repo,prerequisitePath));
  const prerequisite=JSON.parse(prerequisiteBytes).implementation_integrity;
  verifyCurrentCertificate(prerequisite,hotfix,hotfixBytes,hotfixPath);
  const buildPath='reports/engineering/etf-quant-v2-build-integrity.json';
  const buildBytes=readFileSync(repositoryFile(repo,buildPath));
  const build=JSON.parse(buildBytes).implementation_integrity;
  verifyCurrentCertificate(build,prerequisite,prerequisiteBytes,prerequisitePath);
  const finalizationPath='reports/engineering/etf-quant-v2-finalization-integrity.json';
  const finalizationBytes=readFileSync(repositoryFile(repo,finalizationPath));
  const finalization=JSON.parse(finalizationBytes).implementation_integrity;
  verifyCurrentCertificate(finalization,build,buildBytes,buildPath);
  const current=JSON.parse(readFileSync(repositoryFile(repo,'reports/engineering/etf-quant-v2-observation-integrity.json'))).implementation_integrity;
  verifyCurrentCertificate(current,finalization,finalizationBytes,finalizationPath);
  const firewall=Object.entries(current.files).filter(([name,expected])=>
    createHash('sha256').update(readFileSync(repositoryFile(repo,name))).digest('hex')!==expected
  ).map(([name])=>name);
  const documentation=JSON.parse(readFileSync(repositoryFile(repo,'config/engineering/documentation-map.json'),'utf8'));
  for(const item of documentation.documents.filter(item=>item.sha256 && !item.removed_from_tree)) {
    if(createHash('sha256').update(readFileSync(repositoryFile(repo,item.path))).digest('hex')!==item.sha256) firewall.push(item.path);
  }
  const report={status:candidates.length||forbidden.length||sealed.length||firewall.length||remote.embedded_credentials?'BLOCKED':'PASS',
    scanner:'BUILTIN_READ_ONLY_PATTERN_AND_PATH_AUDIT_NOT_A_THIRD_PARTY_CERTIFICATION',
    reviewed_legacy_dummy_template_sha256:'2077e82fcc7bfbccf7eb0f671d597addc90ff9221fae04edef07a81d1178dd2a',
    tracked_files:tracked.length,new_files:extra.length,history_commits:Number(git(['rev-list','--all','--count']).trim()),
    history_blobs_scanned:blobs.length,tracked_secret_candidates:candidates.filter(c=>c.scope==='tracked').length,
    new_secret_candidates:candidates.filter(c=>c.scope==='new').length,history_secret_candidates:candidates.filter(c=>c.scope==='history').length,
    candidates,forbidden_paths:forbidden,sealed_paths_not_read:sealed,large_files_over_500kb:large,firewall_changes:firewall,remote,
    runtime_data_tracked:forbidden.some(c=>c.scope==='tracked'),credential_values_printed:false,
    firewall_policy:'CURRENT_INTEGRITY_WITH_IMMUTABLE_V1_V2_V3_V4_PROVENANCE_AND_RETAINED_ARCHIVE_HASHES',
    public_licensing_review:'MIT_OWNER_AUTHORIZED_DATA_RIGHTS_SEPARATE'};
  return report;
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {const report=audit();process.stdout.write(JSON.stringify(report,null,2)+'\n');process.exitCode=report.status==='PASS'?0:2;}
  catch {process.stdout.write(JSON.stringify({status:'BLOCKED',blocker:'READ_ONLY_SECURITY_AUDIT_BLOCKER',credential_values_printed:false})+'\n');process.exitCode=2;}
}

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
  if(current.identifier==='CURRENT_IMPLEMENTATION_DELTA') {
    if(current.canonicalization!=='JSON_SORTED_KEYS_COMPACT_UTF8_V1'
      || current.parent_manifest_path!==parentPath
      || current.parent_manifest_sha256!==createHash('sha256').update(parentBytes).digest('hex')
      || current.certificate_sha256!==certificateHash(current)
      || new Set(current.changes.map(c=>c.path)).size!==current.changes.length
      || current.changes.length!==Object.keys(current.files).length
      || Object.entries(current.files).some(([name,after])=>!current.changes.some(c=>c.path===name
        && c.before_sha256===(parent.files[name]??null) && c.after_sha256===after)))
      throw new Error('CERTIFICATE_TRANSITION_BLOCKER');
    return {...parent,...current,files:{...parent.files,...current.files}};
  }
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
  return current;
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
// Reviewed aggregate-only V1 closure. Both path and exact bytes must match;
// altered reports and all other research payloads remain prohibited.
const reviewedResearchHashes = Object.freeze({
  'reports/research/swl1_source_qualification/admission-results.json':'c54f8cad06b8f578dfb5b514c825c1bcb38ca13b60b02858c8f102c8ee37922f',
  'reports/research/swl1_source_qualification/data-quality-assessment.json':'854af07e6790e3325270397c08bbe14e8303424c8dc8584ad62d159751aeb282',
  'reports/research/swl1_source_qualification/final-readiness.json':'834456df371b1f704c81e536e61cb702cb184fd3a0a211c0e0e40e388120a539',
  'reports/research/swl1_source_qualification/pit-evidence.json':'4362ca0c917a44292675895e83945045fd9de78dad2b883a482ad2b608d65663',
  'reports/research/swl1_source_qualification/public-evidence.json':'b13cf0561ea85c8a20c359f465543272278ea24c39a8597118d6b1e4495a1975',
  'reports/research/swl1_source_qualification/remediation-matrix.json':'7b6c9f168a1c5a085fdfeb9bb34daa489e2fe0dcc2d882e7c8da6768341f0302',
  'reports/research/swl1_source_qualification/rights-matrix.json':'e97735bba7725c6fad2a4db802312057665982f448bdc72e5a3a767df4693394',
  'reports/research/swl1_source_qualification/source-inventory.json':'2d483c568f84bd6e6b0515b4ab2984a179ca1648c06efffc28c61fcc03e50b74',
  'reports/research/swl1_source_qualification/source-reconciliation.json':'895a75c75b8e0443bbf4e5304cacdde272f3ab403ce874476a8efe2007443bde',
  'reports/research/swl1_data_first/source-inventory.json':'a59cefa8e760900ce0b29170a6f3b3bc2269c2002325ccf3fe0c1c3a834ac8a4',
  'reports/research/swl1_data_first/pit-evidence-assessment.json':'b425233fcc74fbf722ec375c18ef66d7431558eeebbc99edcf5e9bd11c03db49',
  'reports/research/swl1_data_first/source-admission-summary.json':'d5a86b523183eb2ed6705e4133989d8b9f3166d2f4733f37e629f533f7dbbfda',
  'reports/research/swl1_data_first/prospective-readiness.json':'d21f2d7574a46006d5b27cae60f0afefa4acce25fad7d0b7038d3592ba81fbda',
  'reports/research/swl1_failure_forensics/summary.json':'eb67fd6588bd48ffcd13679904bf51e63c62ebfeb5f035b81e9b90f7fe0dadae',
  'reports/research/swl1_failure_forensics/evidence-manifest.json':'b2c40df063112b2c2820a913d6a6e5a0e46369e5530a6fbfd558a17cf413668e',
  'reports/research/swl1_failure_forensics/attribution-matrix.json':'72ffff2424cc5f9f1b897d14ec4854bec45ceaeb7e9f803dc9f66f1ef5000a7c',
  'reports/research/swl1_failure_forensics/next-generation-options.json':'709617fd146ec5a2aa76667b1f5722378120aaa1d0f33e724179a63333f0e378',
  'reports/research/swl1_ridge_v1/data_feasibility.json':'39aff56e15b730bc834cb7407a086546a75f7d4f292ee0cadc38294e1987fad3',
  'reports/research/swl1_ridge_v1/development.json':'a031bec412de2c86008eeb2b9272f8409fd17ce79b8ef511a893d497003dfeda',
  'reports/research/swl1_ridge_v1/factor_audit.json':'c3998b221e4b210271dee6e6e4b6ae118cc4a34717900820425c2d1ef8f9f041',
  'reports/research/swl1_ridge_v1/preregistration.json':'98f3751e7eee900424a05dc28abe53242039477f7dca0e520267fd0741edc8fa',
  'reports/research/swl1_ridge_v1/status.json':'9d2a6b9d418e88008a0125d4004fd9283735ce5fd1b854f7a9de607f73eb6569',
  'reports/research/swl1_ridge_v1/validation.json':'4f39211fb8fcdd3e350355414b753065940b8bdb42bb2ee57a432b89241c205c',
  'reports/research/swl1_ridge_v2/development.json':'8715911746935fcf27200a76d17f402cd95f61f3eaa36312f947c07081be13f2',
  'reports/research/swl1_ridge_v2/validation.json':'e1fea05ccef53c1767f3e8e6b845c9e52e23112543856bbe85095501706dbc97',
  'reports/research/swl1_ridge_v2/status.json':'5453501bbe21068042f9691f3cf900513e6d529a28dd8de3f73b624cc7b6eb85',
});
// Preserve the previously reviewed public bytes in Git history. Every exception
// still requires its exact path and hash; a corrected export adds no broad bypass.
const reviewedHistoricalForensicHashes = Object.freeze({
  'reports/research/swl1_data_first/source-inventory.json':'075b4d07e1fec347ec1e247b7a61fab3dbc47db1af850dd951f352dd7cce0414',
  'reports/research/swl1_failure_forensics/evidence-manifest.json':'a2b3d45de880e1e591c567bd2b8dc951429e812583a7907ea49930597821cc86',
  'reports/research/swl1_failure_forensics/attribution-matrix.json':'993b5e9acb061d075dedaaff3e8a8991a24950892d8badc0e4a46e57d7f38fee',
  'reports/research/swl1_failure_forensics/next-generation-options.json':'17fead746b99caf95504537c04d81344fdcd028c44d2cf0bd6cdc61368a63d61',
});
export const forbiddenData = (name,bytes)=> /^(?:data|runtime|external|lake|exports|cache|logs|secrets)\//.test(name)
  || /(?:^|\/)\.env(?:$|\.(?!example$))/.test(name)
  || /\.(?:db|sqlite3?|h5|hdf5|parquet|p12|pfx)$/.test(name)
  || /(?:^|\/)node_modules\//.test(name)
  || (/^reports\/(backtests|research)\//.test(name) && !name.endsWith('/.gitkeep')
    && !(Object.hasOwn(reviewedResearchHashes,name) && bytes!==undefined
      && (createHash('sha256').update(bytes).digest('hex')===reviewedResearchHashes[name]
        || (Object.hasOwn(reviewedHistoricalForensicHashes,name)
          && createHash('sha256').update(bytes).digest('hex')===reviewedHistoricalForensicHashes[name]))));
const sealedPerformance = name=>/(?:validation|final[_-]?oos)/i.test(name)
  && /(?:performance|predictions|results|returns|metrics)\.(json|csv|parquet)$/i.test(name);

export function audit() {
  const tracked=git(['ls-files','-z']).split('\0').filter(Boolean);
  const extra=git(['ls-files','--others','--exclude-standard','-z']).split('\0').filter(Boolean);
  const candidates=[],large=[],forbidden=[],sealed=[];
  for(const [scope,names] of [['tracked',tracked],['new',extra]]) for(const name of names) {
    if(sealedPerformance(name)){sealed.push({scope,path:name});continue;} // Do NOT inspect sealed content.
    const target=path.join(repo,name), info=lstatSync(target);
    if(info.isSymbolicLink() || !realpathSync(target).startsWith(repo+path.sep)) {
      forbidden.push({scope,path:name,kind:'LINK_OR_CONTAINMENT'});continue;
    }
    if(info.size>500*1024)large.push({scope,path:name,bytes:info.size});
    const bytes=readFileSync(target);
    if(forbiddenData(name,bytes))forbidden.push({scope,path:name});
    const kinds=secretKinds(bytes.toString('utf8'));
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
    if(Number(size)>500*1024)large.push({scope:'history',path:name,blob:id,bytes:Number(size)});
  }
  const content=blobs.length?git(['cat-file','--batch'],blobs.map(([id])=>id).join('\n')+'\n',null):Buffer.alloc(0);
  let offset=0;
  for(const [id,,expectedSize] of blobs) {
    const end=content.indexOf(10,offset),header=content.subarray(offset,end).toString('utf8').split(' ');
    if(header[0]!==id || Number(header[2])!==Number(expectedSize))throw new Error('HISTORY_STREAM_BLOCKER');
    offset=end+1;const size=Number(expectedSize),bytes=content.subarray(offset,offset+size),body=bytes.toString('utf8');offset+=size+1;
    if(forbiddenData(names.get(id)||'',bytes))forbidden.push({scope:'history',path:names.get(id)||'',blob:id});
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
  const observationPath='reports/engineering/etf-quant-v2-observation-integrity.json';
  const observationBytes=readFileSync(repositoryFile(repo,observationPath));
  const observation=JSON.parse(observationBytes).implementation_integrity;
  verifyCurrentCertificate(observation,finalization,finalizationBytes,finalizationPath);
  const factualPath='reports/engineering/etf-quant-v2-factual-refresh-integrity.json';
  const factualBytes=readFileSync(repositoryFile(repo,factualPath));
  const factual=JSON.parse(factualBytes).implementation_integrity;
  verifyCurrentCertificate(factual,observation,observationBytes,observationPath);
  const unitsPath='reports/engineering/etf-quant-v2-factual-units-integrity.json';
  const unitsBytes=readFileSync(repositoryFile(repo,unitsPath));
  const units=JSON.parse(unitsBytes).implementation_integrity;
  verifyCurrentCertificate(units,factual,factualBytes,factualPath);
  const consolePath='reports/engineering/etf-quant-v2-console-integrity.json';
  const consoleBytes=readFileSync(repositoryFile(repo,consolePath));
  const consoleCertificate=JSON.parse(consoleBytes).implementation_integrity;
  verifyCurrentCertificate(consoleCertificate,units,unitsBytes,unitsPath);
  const closurePath='reports/engineering/forward-shadow-closure-integrity.json';
  const closureBytes=readFileSync(repositoryFile(repo,closurePath));
  const closure=JSON.parse(closureBytes).implementation_integrity;
  verifyCurrentCertificate(closure,consoleCertificate,consoleBytes,consolePath);
  const operationsPath='reports/engineering/shadow-operations-integrity.json';
  const operationsBytes=readFileSync(repositoryFile(repo,operationsPath));
  const operations=JSON.parse(operationsBytes).implementation_integrity;
  verifyCurrentCertificate(operations,closure,closureBytes,closurePath);
  const installationPath='reports/engineering/shadow-task-installation-integrity.json';
  const installationBytes=readFileSync(repositoryFile(repo,installationPath));
  const installation=JSON.parse(installationBytes).implementation_integrity;
  verifyCurrentCertificate(installation,operations,operationsBytes,operationsPath);
  const delta=JSON.parse(readFileSync(repositoryFile(repo,'reports/engineering/swl1-source-qualification-integrity.json'))).implementation_integrity;
  const current=verifyCurrentCertificate(delta,installation,installationBytes,installationPath);
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

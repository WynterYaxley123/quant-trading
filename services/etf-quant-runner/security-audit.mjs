/** Read-only Git publication audit; outputs identifiers/counts, NEVER values. */
import {spawnSync} from 'node:child_process';
import {readFileSync,realpathSync,lstatSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
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
  // now permits tooling/formatting there while preserving the certified ETF bytes.
  const integrity=JSON.parse(readFileSync(path.join(repo,'reports/etf_quant/autonomous_code_integrity_v1.json'),'utf8'));
  const firewall=Object.entries(integrity.files).filter(([name,expected])=>
    createHash('sha256').update(readFileSync(path.join(repo,name))).digest('hex')!==expected
  ).map(([name])=>name);
  const report={status:candidates.length||forbidden.length||sealed.length||firewall.length||remote.embedded_credentials?'BLOCKED':'PASS',
    scanner:'BUILTIN_READ_ONLY_PATTERN_AND_PATH_AUDIT_NOT_A_THIRD_PARTY_CERTIFICATION',
    reviewed_legacy_dummy_template_sha256:'2077e82fcc7bfbccf7eb0f671d597addc90ff9221fae04edef07a81d1178dd2a',
    tracked_files:tracked.length,new_files:extra.length,history_commits:Number(git(['rev-list','--all','--count']).trim()),
    history_blobs_scanned:blobs.length,tracked_secret_candidates:candidates.filter(c=>c.scope==='tracked').length,
    new_secret_candidates:candidates.filter(c=>c.scope==='new').length,history_secret_candidates:candidates.filter(c=>c.scope==='history').length,
    candidates,forbidden_paths:forbidden,sealed_paths_not_read:sealed,large_files_over_500kb:large,firewall_changes:firewall,remote,
    runtime_data_tracked:forbidden.some(c=>c.scope==='tracked'),credential_values_printed:false,
    firewall_policy:'CERTIFIED_IMPLEMENTATION_BYTES_UNCHANGED',
    public_licensing_review:'MIT_OWNER_AUTHORIZED_DATA_RIGHTS_SEPARATE'};
  return report;
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {const report=audit();process.stdout.write(JSON.stringify(report,null,2)+'\n');process.exitCode=report.status==='PASS'?0:2;}
  catch {process.stdout.write(JSON.stringify({status:'BLOCKED',blocker:'READ_ONLY_SECURITY_AUDIT_BLOCKER',credential_values_printed:false})+'\n');process.exitCode=2;}
}

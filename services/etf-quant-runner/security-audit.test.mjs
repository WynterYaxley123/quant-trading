import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,symlinkSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {secretKinds,canonicalJSON,certificateHash,repositoryFile,verifyCurrentCertificate} from './security-audit.mjs';

test('private key marker requires review without printing its payload',()=>{
  const sample='-----BEGIN '+'PRIVATE KEY-----';assert.ok(secretKinds(sample).includes('PRIVATE_KEY'));
});
test('empty template and synthetic references are not credential values',()=>{
  assert.deepEqual(secretKinds('API_TOKEN=\npassword=SYNTHETIC_NOT_A_REAL_PASSWORD\napi_key=process.env.API_KEY'),[]);
});
test('high-confidence non-template assignment is a candidate',()=>{
  const sample='api_key='+'FAKE'.repeat(8);assert.ok(secretKinds(sample).includes('CREDENTIAL_ASSIGNMENT'));
});
test('embedded credential URL is blocked but placeholder URL is not',()=>{
  const sample=['https','://','user',':','fake-not-real','@','host.test/path'].join('');
  assert.ok(secretKinds(sample).includes('EMBEDDED_URL_CREDENTIAL'));
  assert.deepEqual(secretKinds('https://<user>:<password>@example.invalid'),[]);
});

function transition() {
  const parent={files:{'a.py':'a'},previous_source_hashes:{z:'z',a:'a'},
    previous_certificate_sha256:'v1',previous_transition_sha256:'v2',candidate_sha256:'candidate'};
  const bytes=Buffer.from(JSON.stringify(parent));
  const current={...structuredClone(parent),identifier:'CURRENT_IMPLEMENTATION_INTEGRITY',
    canonicalization:'JSON_SORTED_KEYS_COMPACT_UTF8_V1',parent_sha:'base',changes:[],
    parent_manifest_path:'reports/engineering/v4-integrity.json',
    parent_manifest_sha256:createHash('sha256').update(bytes).digest('hex')};
  current.certificate_sha256=certificateHash(current);
  return {current,parent,bytes};
}
test('semantic key order accepts equivalent mappings, including nested and numeric keys',()=>{
  const {current,parent,bytes}=transition();
  current.previous_source_hashes={a:'a',z:'z'};
  assert.doesNotThrow(()=>verifyCurrentCertificate(current,parent,bytes));
  assert.equal(canonicalJSON({'2':'two','10':'ten',nested:{'😀':'astral','\uE000':'bmp'}}),
    '{"10":"ten","2":"two","nested":{"":"bmp","😀":"astral"}}');
  assert.equal(certificateHash(current),certificateHash(JSON.parse(JSON.stringify(current))));
});
test('the appended hotfix transition requires the byte-bound previous current manifest path',()=>{
  const {current}=transition();
  const bytes=Buffer.from(JSON.stringify(current));
  const child=structuredClone(current),parentPath='reports/engineering/current-implementation-integrity.json';
  child.parent_manifest_path=parentPath;
  child.parent_manifest_sha256=createHash('sha256').update(bytes).digest('hex');
  child.certificate_sha256=certificateHash(child);
  assert.doesNotThrow(()=>verifyCurrentCertificate(child,current,bytes,parentPath));
  assert.throws(()=>verifyCurrentCertificate(child,current,bytes),/CERTIFICATE_TRANSITION_BLOCKER/);
});
for(const kind of ['changed','missing','extra'])test(`historical source mapping ${kind} fails even with a recomputed digest`,()=>{
  const {current,parent,bytes}=transition();
  if(kind==='changed')current.previous_source_hashes.a='changed';
  if(kind==='missing')delete current.previous_source_hashes.a;
  if(kind==='extra')current.previous_source_hashes.extra='extra';
  current.certificate_sha256=certificateHash(current);
  assert.throws(()=>verifyCurrentCertificate(current,parent,bytes),/CERTIFICATE_TRANSITION_BLOCKER/);
});
for(const field of ['files','changes','parent_sha'])test(`current digest binds ${field}`,()=>{
  const {current,parent,bytes}=transition();
  if(field==='files')current.files['extra.py']='extra';
  if(field==='changes')current.changes.push({path:'extra.py',reason:'tampered'});
  if(field==='parent_sha')current.parent_sha='tampered';
  assert.throws(()=>verifyCurrentCertificate(current,parent,bytes),/CERTIFICATE_TRANSITION_BLOCKER/);
});
test('repository file paths reject traversal, absolute paths and symlink escapes',t=>{
  const temporary=mkdtempSync(path.join(tmpdir(),'audit-path-'));
  t.after(()=>rmSync(temporary,{recursive:true,force:true}));
  const root=path.join(temporary,'repo');mkdirSync(path.join(root,'nested'),{recursive:true});
  const valid=path.join(root,'nested','valid.txt');writeFileSync(valid,'synthetic');
  const outside=path.join(temporary,'outside');writeFileSync(outside,'SYNTHETIC_NEVER_PRINTED');
  assert.equal(repositoryFile(root,'nested/valid.txt'),valid);
  for(const name of ['../outside','nested/../../outside',outside,'C:\\outside','/outside'])
    assert.throws(()=>repositoryFile(root,name),{message:'REPOSITORY_PATH_BLOCKER'});
  try {symlinkSync(outside,path.join(root,'escape'));}
  catch(error) {if(error.code==='EPERM'){t.diagnostic('Symlink creation unavailable; traversal/absolute cases passed.');return;}throw error;}
  assert.throws(()=>repositoryFile(root,'escape'),{message:'REPOSITORY_PATH_BLOCKER'});
});

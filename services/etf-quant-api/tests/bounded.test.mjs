import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,mkdir,open,rm,symlink} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {boundedLeaf,containedExists} from '../bounded.mjs';

test('existence rejects symlink escapes and accepts only contained regular leaves',async t=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'quant-exists-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  await mkdir(path.join(root,'inside'));await mkdir(path.join(root,'outside'));
  await writeFile(path.join(root,'outside/private.json'),'{}');
  await writeFile(path.join(root,'inside/valid.json'),'{}');
  assert.equal(await containedExists(path.join(root,'inside'),'absent.json'),false);
  assert.equal(await containedExists(path.join(root,'inside'),'valid.json'),true);
  await symlink(path.join(root,'outside'),path.join(root,'inside/link'),process.platform==='win32'?'junction':'dir');
  await assert.rejects(containedExists(path.join(root,'inside'),'link/private.json'));
  if(process.platform!=='win32') {
    await symlink(path.join(root,'outside/private.json'),path.join(root,'inside/escape.json'));
    await assert.rejects(containedExists(path.join(root,'inside'),'escape.json'));
  }
  await assert.rejects(containedExists(path.join(root,'inside'),'../outside/private.json'));
});

test('reads enforce the byte ceiling even when a regular file grows after stat',async t=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'quant-bounded-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  await writeFile(path.join(root,'file.json'),'{}');
  const opener=async(...args)=>{
    const handle=await open(...args);
    return {stat:()=>handle.stat(),close:()=>handle.close(),read:async(...values)=>{
      await writeFile(path.join(root,'file.json'),'x'.repeat(4096),{flag:'a'});
      return handle.read(...values);
    }};
  };
  await assert.rejects(boundedLeaf(root,'file.json',32,{opener}),/BOUNDED_FILE/);
  await assert.rejects(boundedLeaf(root,'file.json',32),/BOUNDED_FILE/);
});

test('reads reject directories, traversal and symlink escapes while preserving exact bytes',async t=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'quant-bounded-path-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  await mkdir(path.join(root,'inside'));
  await writeFile(path.join(root,'outside.json'),'secret');
  await writeFile(path.join(root,'inside/file.json'),'{}');
  assert.equal((await boundedLeaf(path.join(root,'inside'),'file.json',2)).raw.toString(),'{}');
  await assert.rejects(boundedLeaf(path.join(root,'inside'),'../outside.json'),/BOUNDED_FILE/);
  await assert.rejects(boundedLeaf(root,'inside'),/BOUNDED_FILE/);
  await symlink(root,path.join(root,'inside/link'),process.platform==='win32'?'junction':'dir');
  await assert.rejects(boundedLeaf(path.join(root,'inside'),'link/outside.json'),/BOUNDED_FILE/);
});

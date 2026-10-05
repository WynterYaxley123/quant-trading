/** Descriptor-bound regular-file reads, including files that grow during observation. */
import {open,realpath,stat,lstat} from 'node:fs/promises';
import path from 'node:path';

export async function containedExists(root,name) {
  const inside=(base,target)=>{
    const relative=path.relative(base,target);
    return relative && relative!=='..' && !relative.startsWith('..'+path.sep) && !path.isAbsolute(relative);
  };
  let base;
  try {base=await realpath(root);} catch(error) {if(error.code==='ENOENT')return false;throw error;}
  const target=path.resolve(base,name);
  if(!inside(base,target))throw new Error('BOUNDED_FILE_INTEGRITY_BLOCKER');
  try {
    // Resolve the parent before even testing existence of a private leaf.
    if(!inside(base,await realpath(path.dirname(target))) && path.dirname(target)!==base)
      throw new Error('BOUNDED_FILE_INTEGRITY_BLOCKER');
    const info=await lstat(target);
    if(!inside(base,await realpath(target)) || !info.isFile())
      throw new Error('BOUNDED_FILE_INTEGRITY_BLOCKER');
    return true;
  } catch(error) {if(error.code==='ENOENT')return false;throw error;}
}

export async function boundedLeaf(root,name,limit=1024*1024,{opener=open}={}) {
  const base=await realpath(root),file=await realpath(path.resolve(base,name));
  const inside=target=>{
    const relative=path.relative(base,target);
    return relative && relative!=='..' && !relative.startsWith('..'+path.sep) && !path.isAbsolute(relative);
  };
  const check=value=>{if(!value)throw new Error('BOUNDED_FILE_INTEGRITY_BLOCKER');};
  check(Number.isSafeInteger(limit) && limit>0 && inside(file));
  const handle=await opener(file,'r');
  try {
    const metadata=await handle.stat(),resolved=await realpath(file),current=await stat(resolved);
    check(inside(resolved) && metadata.isFile() && metadata.size<=limit
      && current.dev===metadata.dev && current.ino===metadata.ino);
    const chunks=[];let total=0;
    for(;;) {
      const chunk=Buffer.alloc(Math.min(65536,limit-total+1));
      const {bytesRead}=await handle.read(chunk,0,chunk.length,null);
      total+=bytesRead;check(total<=limit);
      if(!bytesRead)break;
      chunks.push(chunk.subarray(0,bytesRead));
    }
    return {raw:Buffer.concat(chunks,total),mtime:metadata.mtime.toISOString()};
  } finally {await handle.close();}
}

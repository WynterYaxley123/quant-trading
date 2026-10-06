/** Read-only Windows TCP publication diagnostics; no network/locale changes. */
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

export function excludedRanges(text) {
  if(!/^\s*-{3,}/m.test(text))throw new Error('EXCLUDED_RANGE_OUTPUT_INVALID');
  return text.split(/\r?\n/).flatMap(line=>{
    const match=line.match(/^\s*(\d+)\s+(\d+)\s*\*?\s*$/);
    if(!match)return [];
    const start=Number(match[1]),end=Number(match[2]);
    if(start<1 || end>65535 || start>end)throw new Error('EXCLUDED_RANGE_OUTPUT_INVALID');
    return [[start,end]];
  });
}
export function occupiedPorts(text) {
  if(!/^\s*TCP\s+/im.test(text) && !/^\s*(?:Proto|协议)\s+/im.test(text))throw new Error('TCP_ENDPOINT_OUTPUT_INVALID');
  return text.split(/\r?\n/).flatMap(line=>{
    const match=line.match(/^\s*TCP\s+\S+:(\d+)\s+/i);
    return match?[Number(match[1])]:[];
  });
}
export function evaluate(ports,ranges,occupied) {
  if(!ports.length || new Set(ports).size!==ports.length
    || ports.some(p=>!Number.isInteger(p) || p<1024 || p>65535))throw new Error('DISTINCT_UNPRIVILEGED_PORTS_REQUIRED');
  return ports.map(port=>({port,excluded:ranges.some(([a,b])=>a<=port && port<=b),occupied:occupied.includes(port)}));
}
export function main(args,platform=process.platform,run=spawnSync) {
  if(args.length===1 && args[0]==='--help') {
    console.log('Usage: node scripts/operations/host-ports.mjs --port <1024..65535> [--port <port>]\nWindows read-only TCP reservation/listener check. No settings or services are changed.');
    return 0;
  }
  const ports=[];
  for(let i=0;i<args.length;i+=2){
    if(args[i]!=='--port' || !/^\d+$/.test(args[i+1]??''))throw new Error('ARGUMENTS_INVALID');
    ports.push(Number(args[i+1]));
  }
  evaluate(ports,[],[]);
  if(platform!=='win32')throw new Error('WINDOWS_REQUIRED');
  function read(executable,argv) {
    const result=run(executable,argv,{encoding:'utf8',windowsHide:true,timeout:15000,maxBuffer:1024*1024,shell:false});
    if(result.status!==0 || result.error || !result.stdout)throw new Error('DIAGNOSTIC_COMMAND_BLOCKED');
    return result.stdout;
  }
  const ranges=['ipv4','ipv6'].flatMap(family=>excludedRanges(read('netsh',['interface',family,'show','excludedportrange','protocol=tcp'])));
  const result=evaluate(ports,ranges,occupiedPorts(read('netstat',['-ano'])));
  const safe=result.every(r=>!r.excluded && !r.occupied);
  console.log(JSON.stringify({status:safe?'AVAILABLE_NOW':'BLOCKED',mode:'READ_ONLY',ports:result}));
  // This observation does not reserve ports or authorize service recreation.
  return safe?0:2;
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {process.exitCode=main(process.argv.slice(2));}
  catch {console.error('HOST_PORT_CHECK_BLOCKED; use --help and inspect the local host.');process.exitCode=2;}
}

import test from 'node:test';
import assert from 'node:assert/strict';
import {excludedRanges,occupiedPorts,evaluate,main} from '../operations/host-ports.mjs';

test('localized reservations, inclusive boundaries and wildcard listeners block publication',()=>{
  const ranges=excludedRanges('起始端口 结束端口\n---------- ----------\n 9128 9227 *\n 10000 10001\n');
  const occupied=occupiedPorts(' TCP 0.0.0.0:19200 0.0.0.0:0 LISTENING 123\n TCP [::]:19201 [::]:0 LISTENING 456\n');
  assert.deepEqual(evaluate([9128,9227,19200,19201,19500],ranges,occupied).map(r=>r.excluded||r.occupied),[true,true,true,true,false]);
});
test('invalid ranges, ports, unsupported systems and command failures fail closed',()=>{
  assert.throws(()=>excludedRanges('Access denied'));
  assert.throws(()=>occupiedPorts('Access denied'));
  assert.throws(()=>excludedRanges('-----\n65535 70000'));
  for(const ports of [[],[0],[80],[65536],[19200,19200],[NaN]])assert.throws(()=>evaluate(ports,[],[]));
  assert.throws(()=>main(['--port','19500'],'linux'));
  assert.throws(()=>main(['--port','19500'],'win32',()=>({status:1,stdout:'',stderr:'PRIVATE_VALUE'})));
});
test('adapter runs only read-only argv commands and honors IPv6 exclusions',()=>{
  const calls=[];
  const run=(exe,args,options)=>{
    calls.push([exe,args]);assert.equal(options.shell,false);assert.equal(options.windowsHide,true);
    return {status:0,stdout:exe==='netstat'?' TCP 127.0.0.1:20000 0.0.0.0:0 LISTENING 1\n':`-----\n${args[1]==='ipv6'?'19500 19500':'9128 9227'}\n`};
  };
  assert.equal(main(['--port','19500'],'win32',run),2);
  assert.deepEqual(calls.map(c=>c[0]),['netsh','netsh','netstat']);
  assert.deepEqual(calls[2][1],['-ano']); // Include TCPv6 wildcard listeners too.
});

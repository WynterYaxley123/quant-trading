/** Loopback transport for the existing built dashboard and private offline pack. */
import http from 'node:http';
import path from 'node:path';
import {readFileSync} from 'node:fs';
import {realpath,access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {boundedLeaf} from '../etf-quant-api/bounded.mjs';

const sha=raw=>createHash('sha256').update(raw).digest('hex');
const MODULE_HASH=sha(readFileSync(fileURLToPath(import.meta.url)));
const check=v=>{if(!v)throw new Error('REV10_VIEWER_INTEGRITY_BLOCKER');};
async function pack(root,name,pin) {
  check(path.isAbsolute(root) && /^[a-f0-9]{64}$/.test(pin));
  const real=await realpath(root);check(real===path.resolve(root));
  for(let p=real;;p=path.dirname(p)) {
    try{await access(path.join(p,'.git'));throw new Error('REV10_VIEWER_INTEGRITY_BLOCKER');}
    catch(e){if(e.code!=='ENOENT')throw e;}
    if(path.dirname(p)===p)break;
  }
  const raw=(await boundedLeaf(real,name,256*1024)).raw;check(sha(raw)===pin);
  const manifest=JSON.parse(raw.toString());check(manifest.files && Object.keys(manifest.files).length<=256);
  for(const [file,hash] of Object.entries(manifest.files))check(sha((await boundedLeaf(real,file,4*1024*1024)).raw)===hash);
  return {root:real,manifest};
}
export async function createViewer({repoRoot,bundleRoot,bundlePin,reviewRoot,reviewPin,apiPort}) {
  check(Number.isInteger(apiPort)&&apiPort>=1024&&apiPort<=65535);
  const bundle=await pack(bundleRoot,'bundle-manifest.json',bundlePin),review=await pack(reviewRoot,'delivery-manifest.json',reviewPin);
  check(bundle.manifest.service==='REV10_DASHBOARD_BUNDLE' && review.manifest.private_local_only===true && review.manifest.classification==='EXPLORATORY_POST_HOC' && bundle.manifest.model_hash===review.manifest.model_hash);
  for(const [name,hash] of Object.entries(bundle.manifest.source_sha256)) {
    check(name.startsWith('dashboard/') && !name.includes('..'));
    check(sha((await boundedLeaf(repoRoot,name,4*1024*1024)).raw)===hash);
  }
  const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.json':'application/json'};
  return http.createServer(async(req,res)=>{
    res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
    const error=(status,code)=>{res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({error:code}));};
    if(!/^(127\.0\.0\.1|localhost)(:[0-9]+)?$/.test(req.headers.host??'')||!['127.0.0.1','::1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress))return error(403,'LOCAL_VIEW_ONLY');
    if(req.headers.origin && req.headers.origin!==`http://${req.headers.host}`)return error(403,'ORIGIN_NOT_ALLOWED');
    if(!['GET','HEAD'].includes(req.method))return error(405,'READ_ONLY_VIEWER');
    const url=req.url??'';
    if(url==='/health') {res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({service:'REV10_STATIC_VIEWER',read_only:true,bundle_sha256:bundlePin,review_sha256:reviewPin,model_hash:bundle.manifest.model_hash,module_sha256:MODULE_HASH,api_port:apiPort}));}
    if(url.startsWith('/api/industry-forecast/')&&!url.includes('?')) {
      const upstream=http.request({host:'127.0.0.1',port:apiPort,path:url,method:req.method,headers:{host:`127.0.0.1:${apiPort}`}},answer=>{
        const chunks=[];let length=0;
        answer.on('data',chunk=>{length+=chunk.length;if(length>4*1024*1024){upstream.destroy();return error(502,'UPSTREAM_SIZE_LIMIT');}chunks.push(chunk);});
        answer.on('end',()=>{if(res.writableEnded)return;res.statusCode=answer.statusCode??502;res.setHeader('Content-Type',answer.headers['content-type']??'application/json');res.end(req.method==='HEAD'?undefined:Buffer.concat(chunks));});
      });
      upstream.setTimeout(10000,()=>upstream.destroy());upstream.on('error',()=>{if(!res.writableEnded)error(503,'REV10_API_UNAVAILABLE');});return upstream.end();
    }
    try {
      let chosen=bundle,name=url.slice(1),offline=false;
      if(url.startsWith('/offline-review/')) {chosen=review;name=url.slice('/offline-review/'.length);offline=true;}
      else if(['/','/industry-forecast','/industry-forecast/swl1-rev10','/research','/candidates','/development','/sectors','/diagnostics','/integrity'].includes(url))name='index.html';
      if(!Object.hasOwn(chosen.manifest.files,name))return error(404,'INVALID_VIEW_RESOURCE');
      const raw=(await boundedLeaf(chosen.root,name,4*1024*1024)).raw;check(sha(raw)===chosen.manifest.files[name]);
      res.setHeader('Content-Type',types[path.extname(name)]??'application/octet-stream');
      res.setHeader('Content-Security-Policy',`default-src 'self'; script-src 'self'${offline?" 'unsafe-inline'":''}; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:8787; object-src 'none'; frame-ancestors 'none'`);
      res.end(req.method==='HEAD'?undefined:raw);
    }catch{return error(503,'REV10_VIEWER_INTEGRITY_BLOCKER');}
  });
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const port=Number(process.env.REV10_VIEWER_PORT),repoRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
  check(Number.isInteger(port)&&port>=1024&&port<=65535);
  const server=await createViewer({repoRoot,bundleRoot:process.env.REV10_BUNDLE_ROOT,bundlePin:process.env.REV10_BUNDLE_SHA256,reviewRoot:process.env.REV10_REVIEW_ROOT,reviewPin:process.env.REV10_REVIEW_SHA256,apiPort:Number(process.env.INDUSTRY_FORECAST_API_PORT)});
  server.listen(port,'127.0.0.1',()=>process.stdout.write(`REV10_READ_ONLY_VIEWER 127.0.0.1:${port}\n`));
}

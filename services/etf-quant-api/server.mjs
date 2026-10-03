/** Independent read-only observer. Built-in Node modules only; no Research adapter. */
import http from 'node:http';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { readFile, realpath, stat, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
import { aggregateCurrent, projectCurrent } from './current.mjs';
import { allowedOrigins } from './origins.mjs';

export const strategy = JSON.parse(await readFile(new URL('./strategy.json', import.meta.url), 'utf8'));
export const PREFIX = '/api/etf-quant/v1/';
export const ENDPOINTS = Object.freeze({
  status: 'status', strategy: 'strategy', models: 'models',
  'rankings/10d': ['rankings', '10d'], 'rankings/40d': ['rankings', '40d'],
  'rankings/120d': ['rankings', '120d'], 'rankings/fusion': ['rankings', 'fusion'],
  'portfolio/summary': 'portfolio_summary', 'portfolio/holdings': 'holdings', 'portfolio/nav': 'nav',
  trades: 'trades', mappings: 'mappings', 'benchmark/csi300': 'benchmark', health: 'health',
  readiness: 'readiness',
  current: 'current',
});
export const READINESS_DEFAULT = Object.freeze({contract:'SHADOW_START_READINESS_V1',generated_at:null,
  data_cutoff:null,overall:'NOT_REACHED',gates:[],shadow_epoch_created:false,shadow_started:false,notes:[]});
const GATE_STATUSES = new Set(['PASS','BLOCKED','NOT_REACHED','DEFERRED','UNKNOWN']);
const HASH = /^[a-f0-9]{64}$/;
const ID = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/;
const sha = b => createHash('sha256').update(b).digest('hex');
class IntegrityError extends Error { constructor() { super('RUNTIME_INTEGRITY_BLOCKER'); } }
const invariant = condition => { if (!condition) throw new IntegrityError(); };

export function emptyView(reason = 'NO_SUCCESSFUL_RUNTIME_RUN') {
  return {
    status: {product:'ETF_QUANT',version:'ETF_QUANT_V1',mode:'SIMULATION_ONLY',phase:'NOT_STARTED',reason,
      snapshot_id:null,source_commit:null,source_version:null,code_commit:null,cutoff:null,updated_at:null,
      signal_date:null,execution_date:null,epoch:null,mapping_hash:null,strategy_hash:null,
      broker_enabled:false,real_order_path:false,validation_opened:false,final_oos_read:false},
    strategy,models:[],rankings:{'10d':[],'40d':[],'120d':[],fusion:[]},
    portfolio_summary:{status:'NOT_STARTED',cash:null,market_value:null,total_equity:null,initial_cash:'10000',
      realized_pnl:null,unrealized_pnl:null,total_return:null,total_pnl:null,daily_return:null,turnover:null,
      turnover_definition:'CUMULATIVE_ABSOLUTE_SLIPPED_NOTIONAL_DIVIDED_BY_INITIAL_CASH',
      max_drawdown:null,sharpe:null,rebalance_count:null,last_rebalance_at:null},
    holdings:[],nav:[],trades:[],mappings:{status:'MAPPING_ADMISSION_BLOCKED',reason:'NO_VERIFIED_EVIDENCE',entries:[],diagnostics:[]},
    benchmark:{symbol:'000300.SH',status:'NOT_STARTED',points:[],nasdaq:'DEFERRED',sp500:'DEFERRED',model_input:false},
    health:{status:'NOT_STARTED',blockers:[reason],quality_flags:['HISTORICAL_MEMBERSHIP_PIT_UNPROVEN'],
      adjustment_exact_rows:null,adjustment_rejected_rows:null,coverage:null,strict_tls:'SIDECAR_ONLY_NO_TLS_OVERRIDE',historical_performance:false},
  };
}

async function contained(root, relative) {
  const resolved = await realpath(path.join(root, relative));
  const remainder = path.relative(root, resolved);
  invariant(remainder && !remainder.startsWith('..') && !path.isAbsolute(remainder));
  return resolved;
}
async function readSmall(file, limit = 32 * 1024 * 1024) {
  const info = await stat(file);
  invariant(info.isFile() && info.size <= limit);
  return readFile(file);
}
async function fileHash(file) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
async function externalRoot(root) {
  invariant(path.isAbsolute(root));
  const resolved = await realpath(root);
  for (let p = resolved; ; p = path.dirname(p)) {
    try { await access(path.join(p,'.git')); throw new IntegrityError(); }
    catch (e) { if (e instanceof IntegrityError || e.code !== 'ENOENT') throw e; }
    if (path.dirname(p) === p) break;
  }
  return resolved;
}
export async function generation(root, pointer, required) {
  invariant(pointer && ID.test(pointer.run_id) && HASH.test(pointer.manifest_sha256));
  const runRoot = await contained(root, pointer.run_id);
  const raw = await readSmall(await contained(runRoot,'manifest.json'), 1024 * 1024);
  invariant(sha(raw) === pointer.manifest_sha256);
  const manifest = JSON.parse(raw);
  invariant(manifest.schema_version === '1.0.0' && manifest.run_id === pointer.run_id
    && manifest.files && Object.keys(manifest.files).sort().join('|') === [...required].sort().join('|'));
  const bodies = {};
  for (const [name, hash] of Object.entries(manifest.files)) {
    invariant(/^[a-z_]+[.]json$/.test(name) && HASH.test(hash));
    const file = await contained(runRoot,name);
    if (name === 'view.json' || name === 'failure.json') {
      bodies[name] = await readSmall(file);
      invariant(sha(bodies[name]) === hash);
    } else {
      invariant(await fileHash(file) === hash); // Never expose or parse private state/prefix.
    }
  }
  return {manifest,bodies};
}

function safeTree(value, depth=0) {
  invariant(depth < 40);
  if (typeof value === 'string') invariant(!/^(?:[a-zA-Z]:[\\/]|file:|\/|\\\\)/.test(value));
  if (typeof value === 'number') invariant(Number.isFinite(value));
  if (value && typeof value === 'object') for (const [key, child] of Object.entries(value)) {
    invariant(!/^(token|password|secret|authorization|cookie|api[_-]?key|api[_-]?token|app[_-]?secret|access[_-]?token|credentials|private_key|stack|traceback)$/i.test(key));
    safeTree(child,depth+1);
  }
}
function validateView(view, now) {
  invariant(view && view.status?.product === 'ETF_QUANT' && view.status?.version === 'ETF_QUANT_V1'
    && view.status?.mode === 'SIMULATION_ONLY' && view.status.broker_enabled === false
    && view.status.real_order_path === false && view.status.validation_opened === false && view.status.final_oos_read === false);
  invariant(['models','holdings','nav','trades'].every(k=>Array.isArray(view[k]))
    && ['10d','40d','120d','fusion'].every(k=>Array.isArray(view.rankings?.[k]))
    && view.benchmark?.symbol === '000300.SH' && view.benchmark.model_input === false
    && view.benchmark.nasdaq === 'DEFERRED' && view.benchmark.sp500 === 'DEFERRED'
    && view.strategy?.model === 'Ridge' && view.strategy.alpha === .01 && view.strategy.top_k === 5
    && view.portfolio_summary && view.mappings && view.health);
  for (const k of ['version','mode','currency','initial_cash','model','alpha','training_window_months','minimum_training_days',
    'window_anchor','target','preprocessing','horizons','h10_factors','h40_factors','h120_factors','fusion','zscore_ddof','top_k',
    'target_weight_cap','weighting','execution','bookkeeping','source_c_identity','construction','pit_quality','factor_registry']) {
    invariant(isDeepStrictEqual(view.strategy[k],strategy[k]));
  }
  const b40 = view.strategy.execution_policy === 'B40_WITH_CASH';
  if (b40) {
    invariant(view.status.execution_policy === 'B40_WITH_CASH'
      && view.strategy.rebalance === 'EXECUTABLE_MEMBER_SET_CHANGE_INCLUDING_EXECUTABILITY_V1'
      && view.strategy.cash_semantics === 'UNALLOCATED_EXECUTION_CAPACITY'
      && view.mappings.status === 'READY' && Array.isArray(view.mappings.slots)
      && view.mappings.slots.length === 5 && Array.isArray(view.mappings.entries));
    const slots = view.mappings.slots;
    invariant(new Set(slots.map(s=>s.industry_code)).size===5
      && new Set(slots.filter(s=>s.etf_code).map(s=>s.etf_code)).size===view.mappings.entries.length
      && slots.filter(s=>s.etf_code).length===view.mappings.entries.length
      && slots.every(s=>s.etf_code===null || ['STRICT_MAPPING','PROXY_EXPOSURE'].includes(s.mapping_type))
      && slots.every(s=>s.etf_code!==null || s.mapping_type==='CASH_UNEXECUTABLE_SIGNAL'
        && s.execution_reason==='NO_ORDER_UNEXECUTABLE_SIGNAL')
      && slots.every(s=>!s.etf_code || Date.parse(s.evidence_available_at)<=Date.parse(view.status.updated_at))
      && Math.abs(slots.reduce((n,s)=>n+s.target_weight,0)-1)<1e-9
      && Math.abs(slots.reduce((n,s)=>n+s.cash_retained_weight,0)-view.mappings.cash_weight)<1e-9
      && Math.abs(view.mappings.cash_weight+view.mappings.risk_asset_weight-1)<1e-9);
  } else invariant(view.strategy.execution_policy===undefined && view.strategy.rebalance===strategy.rebalance);
  const money = v=>typeof v==='string' && /^-?\d+(\.\d+)?$/.test(v) && Number.isFinite(Number(v));
  invariant(Number.isInteger(view.strategy.lot_size) && view.strategy.lot_size>0);
  invariant(Object.values(view.strategy.costs).every(v=>money(v) && Number(v)>=0));
  const updated = Date.parse(view.status.updated_at);
  invariant(Number.isFinite(updated) && updated<=now);
  // Formal T0 instance is NOT the legacy T1 account. At T0 the public
  // accounting summary remains null, and no fill/NAV is fabricated.
  if (view.status.shadow_epoch || view.status.formal_signal) {
    const e=view.status.shadow_epoch, s=view.status.formal_signal;
    invariant(b40 && e && s && view.status.shadow_epoch_created===true
      && e.simulation_only===true && e.broker_enabled===false && e.real_order_path===false
      && s.simulation_only===true && s.broker_enabled===false && s.real_order_path===false
      && e.epoch_id===s.epoch_id && e.candidate_hash===s.candidate_hash
      && e.initial_capital==='10000' && e.initial_cash==='10000'
      && Array.isArray(e.initial_positions) && e.initial_positions.length===0
      && HASH.test(e.candidate_hash) && HASH.test(s.pit_registry_hash) && HASH.test(s.strict_registry_hash)
      && /^[a-f0-9]{40}$/.test(s.code_sha) && s.code_sha===view.status.code_commit
      && Date.parse(e.created_at)<=updated && Date.parse(s.decision_at)===updated
      && Date.parse(e.available_from)<=Date.parse(e.created_at) && Date.parse(s.available_from)<=updated
      && e.source_commit===view.status.source_commit && s.source_commit===view.status.source_commit
      && e.first_signal_date<=s.signal_date && s.signal_date===view.status.signal_date
      && s.signal_date===view.status.cutoff && s.signal_date!=='2026-09-24' && e.first_signal_date!=='2026-09-24'
      && s.slots.length===5 && isDeepStrictEqual(s.slots,view.mappings.slots)
      && Math.abs(s.risk_asset_weight+s.cash_weight-1)<1e-9);
    if (view.status.epoch) invariant(view.status.epoch.shadow_epoch_id===e.epoch_id);
  }
  invariant(view.models.length===0 || (view.models.length===3 && new Set(view.models.map(m=>m.horizon)).size===3));
  for (const m of view.models) {
    const names=m.horizon===10?strategy.h10_factors:m.horizon===40?strategy.h40_factors:m.horizon===120?strategy.h120_factors:null;
    invariant(names && m.alpha===.01 && JSON.stringify(m.factor_names)===JSON.stringify(names)
      && m.coefficients.length===names.length && m.coefficients.every(Number.isFinite) && Number.isFinite(m.intercept)
      && m.available_at===null && m.source_published_at===null && HASH.test(m.model_hash)
      && m.training?.training_day_count>=30 && m.training.training_end<=m.training.label_cutoff
      && m.training.label_cutoff<=view.status.cutoff && Date.parse(m.current_snapshot_observed_at)<=updated);
  }
  if (!view.status.epoch) invariant(view.nav.length === 0 && view.holdings.length === 0 && view.trades.length === 0
    && view.benchmark.points.length===0
    && ['cash','market_value','total_equity','realized_pnl','unrealized_pnl','total_return','total_pnl','daily_return','turnover','max_drawdown','sharpe','rebalance_count']
      .every(k=>view.portfolio_summary[k] === null));
  if (view.status.epoch) {
    const start = Date.parse(view.status.epoch.started_at);
    invariant(Number.isFinite(start) && start<=updated && view.portfolio_summary.status==='RUNNING');
    const summary=view.portfolio_summary;
    invariant(['cash','market_value','total_equity'].every(k=>money(summary[k]) && Number(summary[k])>=0));
    invariant(Math.abs(Number(summary.total_equity)-Number(summary.cash)-Number(summary.market_value))<1e-7);
    const days=view.nav.map(p=>p.trade_date);
    invariant(new Set(days).size===days.length && days.every((d,i)=>i===0 || d>days[i-1]));
    invariant(view.nav.every(p=>Date.parse(p.timestamp) >= start && Date.parse(p.timestamp)<=updated
      && p.trade_date>=view.status.epoch.market_cutoff && money(p.normalized_nav) && Number(p.normalized_nav)>=0));
    invariant(new Set(view.holdings.map(p=>p.asset_id)).size===view.holdings.length
      && view.holdings.every(p=>money(p.quantity) && Number(p.quantity)>0 && Number(p.quantity)%view.strategy.lot_size===0));
    invariant(view.benchmark.points.every(p=>days.includes(p.trade_date)));
    invariant(view.trades.every(t=>t.intent?.mode==='SIMULATION_ONLY' && ['BUY','SELL'].includes(t.intent.side)
      && Date.parse(t.processed_at)>=start && Date.parse(t.processed_at)<=updated && t.executed_at===t.processed_at
      && Date.parse(t.intent_persisted_at)<Date.parse(t.market_execution_at)
      && Date.parse(t.market_execution_at)<=Date.parse(t.processed_at)));
    if (b40) invariant(view.trades.every(t=>t.accounting_mode==='DELAYED_T1_OPEN_ACCOUNTING'
      && t.execution_evidence==='NOT_REALTIME_EXECUTION_EVIDENCE'
      && t.economic_execution_at===t.market_execution_at
      && Date.parse(t.economic_execution_at)<Date.parse(t.evidence_available_at)
      && Date.parse(t.evidence_available_at)<=Date.parse(t.processed_at)
      && t.intent.asset_id!=='CASH'));
  }
  safeTree(view);
}

export async function observe(root, now = Date.now()) {
  if (!root) return {view:emptyView('RUNTIME_ROOT_NOT_CONFIGURED'),pointer:null};
  root = await externalRoot(root);
  let pointer = null, attemptPointer = null, view = emptyView();
  let latestRaw;
  try { latestRaw = await readSmall(await contained(root,'latest.json'),4096); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (latestRaw) {
    pointer = JSON.parse(latestRaw);
    const {bodies,manifest} = await generation(await contained(root,'runs'),pointer,['view.json','state.json','prefix.json']);
    invariant(manifest.status === 'SUCCESSFUL_OBSERVATION');
    view = JSON.parse(bodies['view.json']);
    validateView(view, now);
    invariant(view.status.snapshot_id === manifest.snapshot_id && view.status.mapping_hash === manifest.mapping_hash
      && view.status.strategy_hash === manifest.strategy_hash && view.status.code_commit === manifest.code_commit);
    if (now - Date.parse(view.status.updated_at) > 48 * 60 * 60 * 1000) view.health.freshness = 'STALE';
    else view.health.freshness = 'CURRENT';
  }
  let failureRaw;
  try { failureRaw = await readSmall(await contained(root,'last_attempt.json'),4096); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (failureRaw) {
    const failedPointer = JSON.parse(failureRaw);
    attemptPointer = failedPointer;
    const {manifest,bodies} = await generation(await contained(root,'failures'),failedPointer,['failure.json']);
    const failure = JSON.parse(bodies['failure.json']);
    invariant(manifest.status === 'FAILED' && failure.status === 'FAILED' && /^[A-Z0-9_]+$/.test(failure.blocker)
      && Number.isFinite(Date.parse(failure.processed_at)) && Date.parse(failure.processed_at)<=now
      && failure.validation_opened===false && failure.final_oos_read===false);
    safeTree(failure);
    if (!view.status.updated_at || Date.parse(failure.processed_at) > Date.parse(view.status.updated_at)) {
      view.health.status = 'DEGRADED';
      view.health.blockers = [failure.blocker];
      view.health.last_attempt_status = 'FAILED';
      view.health.last_attempt_at = failure.processed_at;
      if (!pointer) {
        view.status.phase='DATA_ADMISSION_BLOCKED';view.status.reason=failure.blocker;
        view.status.updated_at=failure.processed_at;
        view.status.source_commit=failure.source_commit ?? null;
      }
    }
  }
  return {view,pointer,attemptPointer};
}

function validateReadiness(doc, now) {
  invariant(doc && doc.contract==='SHADOW_START_READINESS_V1' && Array.isArray(doc.gates)
    && Array.isArray(doc.notes) && doc.gates.length<=64 && doc.notes.length<=64);
  invariant(doc.generated_at===null || Number.isFinite(Date.parse(doc.generated_at)) && Date.parse(doc.generated_at)<=now);
  invariant(doc.data_cutoff===null || /^\d{4}-\d{2}-\d{2}$/.test(doc.data_cutoff));
  invariant(['PASS','BLOCKED','NOT_REACHED'].includes(doc.overall));
  // This V1 artifact is a pre-shadow gate record; a started epoch contradicts it by construction.
  invariant(doc.shadow_epoch_created===false && doc.shadow_started===false);
  invariant(doc.notes.every(n=>typeof n==='string' && n.length<=300));
  for (const g of doc.gates) {
    invariant(g && typeof g.name==='string' && /^[A-Z0-9_]{1,64}$/.test(g.name) && GATE_STATUSES.has(g.status)
      && typeof g.summary==='string' && g.summary.length<=500
      && (g.evidence===null || typeof g.evidence==='string' && g.evidence.length<=300));
  }
  const blocked=doc.gates.some(g=>g.status==='BLOCKED'), allPass=doc.gates.length>0 && doc.gates.every(g=>g.status==='PASS');
  if (blocked) invariant(doc.overall==='BLOCKED');
  else if (allPass) invariant(doc.overall==='PASS');
  else invariant(doc.overall!=='PASS');
  safeTree(doc);
}
export async function observeReadiness(root, now = Date.now()) {
  if (!root) return READINESS_DEFAULT;
  root = await externalRoot(root);
  let raw;
  try { raw = await readSmall(await contained(root,'readiness.json'),1024*1024); }
  catch (error) { if (error.code === 'ENOENT') return READINESS_DEFAULT; throw error; }
  const doc = JSON.parse(raw);
  validateReadiness(doc, now);
  return doc;
}

export function createApi({runtimeRoot='',controlRoot='',repoRoot,now=()=>Date.now(),origins=allowedOrigins()}={}) {
  return http.createServer(async (req,res)=>{
    res.setHeader('Content-Type','application/json; charset=utf-8');
    res.setHeader('Cache-Control','no-store');
    res.setHeader('X-Content-Type-Options','nosniff');
    const respond = (status,data=null,code=null,meta={}) => {
      res.statusCode=status;
      const payload=JSON.stringify({schemaVersion:'1.0.0',data,error:code?{code,message:code}:null,meta});
      res.end(req.method==='HEAD'?undefined:payload);
    };
    if (!/^(127\.0\.0\.1|localhost)(:[0-9]+)?$/.test(req.headers.host ?? '')) return respond(403,null,'LOCAL_HOST_REQUIRED');
    const origin=req.headers.origin;
    if (origin && !origins.has(origin)) return respond(403,null,'ORIGIN_NOT_ALLOWED');
    if (origin) {res.setHeader('Access-Control-Allow-Origin',origin);res.setHeader('Vary','Origin');}
    if (!['GET','HEAD','OPTIONS'].includes(req.method)) {res.setHeader('Allow','GET, HEAD, OPTIONS');return respond(405,null,'READ_ONLY_API');}
    const url=req.url ?? '';
    if (url.includes('%') || url.includes('\\') || url.includes('..') || url.includes('//') || url.includes('?')
      || !url.startsWith(PREFIX)) return respond(400,null,'INVALID_RESOURCE');
    const resource=url.slice(PREFIX.length);
    if (!Object.hasOwn(ENDPOINTS,resource)) return respond(404,null,'RESOURCE_NOT_FOUND');
    if (req.method==='OPTIONS') {res.setHeader('Access-Control-Allow-Methods','GET, HEAD, OPTIONS');return respond(204);}
    try {
      const {view,pointer,attemptPointer}=await observe(runtimeRoot,now());
      const current=(controlRoot || resource==='current')
        ? await aggregateCurrent({controlRoot,repoRoot,view,pointer,now:now()}) : null;
      if(current && controlRoot) projectCurrent(view,current);
      const route=ENDPOINTS[resource];
      const data=resource==='current'?current:resource==='readiness'?await observeReadiness(runtimeRoot,now())
        :Array.isArray(route)?view[route[0]][route[1]]:view[route];
      return respond(200,data,null,{runId:pointer?.run_id ?? null,manifestSha256:pointer?.manifest_sha256 ?? null,
        attemptRunId:attemptPointer?.run_id ?? null,attemptManifestSha256:attemptPointer?.manifest_sha256 ?? null,etfQuant:true});
    } catch {return respond(503,null,'RUNTIME_INTEGRITY_BLOCKER');}
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const port=Number(process.env.ETF_QUANT_API_PORT || 3312);
  if (!Number.isInteger(port) || port<1024 || port>65535) throw new Error('INVALID_LOCAL_PORT');
  const server=createApi({runtimeRoot:process.env.ETF_QUANT_RUNTIME_ROOT || '',
    controlRoot:process.env.ETF_QUANT_CONTROL_ROOT || ''});
  server.listen(port,'127.0.0.1',()=>process.stdout.write(`ETF_QUANT_READ_ONLY_API 127.0.0.1:${port}\n`));
}

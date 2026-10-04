import { currentStatusSchema,endpointSchemas,envelopeSchema,readinessSchema,snapshotSchema,statusSchema,type EtfEndpoint,type EtfQuantCurrentStatus,type EtfQuantReadiness,type EtfQuantSnapshot,type EtfQuantStatus } from './contracts';
import { v2ResearchSchema, v2CurrentSchema, type V2Research, type V2Current } from './v2-contracts';

export interface EtfQuantDataPort {
  getStatus(signal?:AbortSignal):Promise<EtfQuantStatus>;
  getSnapshot(signal?:AbortSignal):Promise<EtfQuantSnapshot>;
  getReadiness(signal?:AbortSignal):Promise<EtfQuantReadiness>;
  getCurrentStatus?(signal?:AbortSignal):Promise<EtfQuantCurrentStatus>;
  getV2Research?(signal?:AbortSignal):Promise<V2Research>;
  getV2Current?(signal?:AbortSignal):Promise<V2Current>;
}
export class EtfQuantDataError extends Error {
  constructor(readonly code:'UNREACHABLE'|'INVALID_RESPONSE'|'GENERATION_CHANGED'|'INTEGRITY_BLOCKED') {
    super(code==='UNREACHABLE'?'ETF Quant 接口未连接。':code==='GENERATION_CHANGED'?'ETF Quant 快照已更新，请手动刷新。':'ETF Quant 数据完整性检查未通过。');
  }
}
export function createEtfQuantApi(base='http://127.0.0.1:3312',transport:typeof fetch=fetch):EtfQuantDataPort {
  const origin=new URL(base);
  if (origin.protocol!=='http:' || !['localhost','127.0.0.1'].includes(origin.hostname)
    || origin.username || origin.password || origin.pathname!=='/' || origin.search || origin.hash) throw new EtfQuantDataError('INVALID_RESPONSE');
  async function read(endpoint:EtfEndpoint,signal?:AbortSignal) {
    try {
      const timed=AbortSignal.timeout(10000);
      const response=await transport(`${origin.origin}/api/etf-quant/v1/${endpoint}`,{method:'GET',signal:signal?AbortSignal.any([signal,timed]):timed,credentials:'omit'});
      if (!response.ok) throw new EtfQuantDataError('INTEGRITY_BLOCKED');
      const envelope=envelopeSchema.parse(await response.json());
      return {...envelope,data:endpointSchemas[endpoint].parse(envelope.data)};
    } catch (error) {
      if (error instanceof EtfQuantDataError) throw error;
      throw new EtfQuantDataError(error instanceof TypeError || (error instanceof Error && error.name==='TimeoutError')?'UNREACHABLE':'INVALID_RESPONSE');
    }
  }
  return {
    async getV2Current(signal) {
      try {
        const timed=AbortSignal.timeout(10000);
        const response=await transport(`${origin.origin}/api/etf-quant/v2/current`,{method:'GET',signal:signal?AbortSignal.any([signal,timed]):timed,credentials:'omit'});
        if(!response.ok)throw new EtfQuantDataError('INTEGRITY_BLOCKED');
        return v2CurrentSchema.parse(envelopeSchema.parse(await response.json()).data);
      } catch(error) {
        if(error instanceof EtfQuantDataError)throw error;
        throw new EtfQuantDataError(error instanceof TypeError?'UNREACHABLE':'INVALID_RESPONSE');
      }
    },
    async getV2Research(signal) {
      try {
        const timed=AbortSignal.timeout(10000);
        const response=await transport(`${origin.origin}/api/etf-quant/v2/research`,{method:'GET',signal:signal?AbortSignal.any([signal,timed]):timed,credentials:'omit'});
        if(!response.ok) throw new EtfQuantDataError('INTEGRITY_BLOCKED');
        return v2ResearchSchema.parse(envelopeSchema.parse(await response.json()).data);
      } catch(error) {
        if(error instanceof EtfQuantDataError) throw error;
        throw new EtfQuantDataError(error instanceof TypeError?'UNREACHABLE':'INVALID_RESPONSE');
      }
    },
    async getCurrentStatus(signal) {
      try {
        const timed=AbortSignal.timeout(10000);
        const response=await transport(`${origin.origin}/api/etf-quant/v1/current`,{method:'GET',
          signal:signal?AbortSignal.any([signal,timed]):timed,credentials:'omit'});
        if(!response.ok) throw new EtfQuantDataError('INTEGRITY_BLOCKED');
        return currentStatusSchema.parse(envelopeSchema.parse(await response.json()).data);
      } catch(error) {
        if(error instanceof EtfQuantDataError) throw error;
        throw new EtfQuantDataError(error instanceof TypeError?'UNREACHABLE':'INVALID_RESPONSE');
      }
    },
    async getStatus(signal) {return statusSchema.parse((await read('status',signal)).data);},
    async getReadiness(signal) {
      try {
        const timed=AbortSignal.timeout(10000);
        const response=await transport(`${origin.origin}/api/etf-quant/v1/readiness`,{method:'GET',signal:signal?AbortSignal.any([signal,timed]):timed,credentials:'omit'});
        if (!response.ok) throw new EtfQuantDataError('INTEGRITY_BLOCKED');
        const envelope=envelopeSchema.parse(await response.json());
        return readinessSchema.parse(envelope.data);
      } catch (error) {
        if (error instanceof EtfQuantDataError) throw error;
        throw new EtfQuantDataError(error instanceof TypeError || (error instanceof Error && error.name==='TimeoutError')?'UNREACHABLE':'INVALID_RESPONSE');
      }
    },
    async getSnapshot(signal) {
      const names=Object.keys(endpointSchemas) as EtfEndpoint[];
      const replies=await Promise.all(names.map(name=>read(name,signal)));
      const generations=new Set(replies.map(r=>`${r.meta.runId}:${r.meta.manifestSha256}:${r.meta.attemptRunId ?? null}:${r.meta.attemptManifestSha256 ?? null}`));
      if(generations.size!==1) throw new EtfQuantDataError('GENERATION_CHANGED');
      const values=Object.fromEntries(names.map((name,i)=>[name,replies[i]?.data]));
      return snapshotSchema.parse({status:values.status,strategy:values.strategy,models:values.models,
        rankings:{'10d':values['rankings/10d'],'40d':values['rankings/40d'],'120d':values['rankings/120d'],fusion:values['rankings/fusion']},
        portfolio_summary:values['portfolio/summary'],holdings:values['portfolio/holdings'],nav:values['portfolio/nav'],trades:values.trades,
        mappings:values.mappings,benchmark:values['benchmark/csi300'],health:values.health});
    },
  };
}
let override:EtfQuantDataPort|null=null;
let singleton:EtfQuantDataPort|null=null;
export function setEtfQuantPortForTesting(port:EtfQuantDataPort|null) {override=port;}
export function getEtfQuantPort():EtfQuantDataPort {
  if(override) return override;
  // Existing Research mock tests do not implicitly opt into a second product.
  // There is NO synthetic ETF adapter or automatic fallback in production.
  if(import.meta.env.MODE==='test') return disabledPort;
  singleton ??= createEtfQuantApi(import.meta.env.VITE_ETF_QUANT_API_BASE_URL || 'http://127.0.0.1:3312');
  return singleton;
}
const disabledPort:EtfQuantDataPort={
  async getStatus(){throw new EtfQuantDataError('UNREACHABLE');},
  async getSnapshot(){throw new EtfQuantDataError('UNREACHABLE');},
  async getReadiness(){throw new EtfQuantDataError('UNREACHABLE');},
};

import {afterEach,expect,it} from 'vitest';
import {screen} from '@testing-library/react';
import {v2ResearchSchema} from '@/etf-quant/v2-contracts';
import {createEtfQuantApi,setEtfQuantPortForTesting} from '@/etf-quant/data-port';
import {renderApp} from './test-utils';
import {etfFixture,notReachedReadiness} from './etf-quant-fixtures';

const synthetic={product:'ETF_QUANT_V2',research_status:'VALIDATION_INFORMED_NOT_INDEPENDENTLY_VALIDATED',candidate_sha256:'a'.repeat(64),
  evidence_mode:'HIGH_CONFIDENCE',specification:{identifier:'SYNTHETIC',family:'S2A',horizons:[10,40,120],fusion:[.25,.5,.25],alpha:30,
    training_months:12,scaling:'RAW',factors:Array.from({length:19},(_,i)=>`f${i}`),h10_factors:Array.from({length:5},(_,i)=>`h${i}`)},
  historical_start:'2018-01-02',historical_end:'2026-09-24',trading_sessions:2120,history_years:8.7,membership_tier_rows:{A:0,B:100,C:10,D:1},
  development:{signals:230,mean_rank_ic:.14,mean_spread:.03},validation_status:'FAILED',validation:{signals:80,mean_rank_ic:.005,mean_spread:-.0008},
  revision_independently_validated:false,final_oos_opened:false,shadow_ready:true,shadow_started:false,epoch_count:0,signal_count:0,intent_count:0,fill_count:0,
  broker_enabled:false,real_order_path:false,limitations:['SYNTHETIC']};
afterEach(()=>setEtfQuantPortForTesting(null));
it('V2 card states failed Validation and unvalidated revision separately from V1',async()=>{
  const data=etfFixture(),readiness=notReachedReadiness();setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},
    async getReadiness(){return readiness;},async getV2Research(){return v2ResearchSchema.parse(synthetic);}});
  await renderApp('/etf-quant/overview');
  expect(await screen.findByText(/原候选 Validation 未通过/)).toBeInTheDocument();
  expect(screen.getByText(/epoch \/ signal \/ intent \/ fill 均为 0/)).toBeInTheDocument();
  expect(screen.getByText(/尚未独立验证/)).toBeInTheDocument();
});
it('V2 DTO rejects OOS/Shadow/broker activation and forged validation success',()=>{
  for(const patch of [{final_oos_opened:true},{shadow_started:true},{broker_enabled:true},{validation_status:'ACCEPTED'},{epoch_count:1}])
    expect(v2ResearchSchema.safeParse({...synthetic,...patch}).success).toBe(false);
});
it('V2 adapter uses the independent read-only endpoint and fails on malformed evidence',async()=>{
  const requested:string[]=[];
  const api=createEtfQuantApi('http://127.0.0.1:3312',async input=>{
    requested.push(String(input));return new Response(JSON.stringify({schemaVersion:'1.0.0',data:synthetic,error:null,meta:{runId:null,manifestSha256:null,etfQuant:true}}));
  });
  expect((await api.getV2Research!()).validation_status).toBe('FAILED');
  expect(requested).toEqual(['http://127.0.0.1:3312/api/etf-quant/v2/research']);
});

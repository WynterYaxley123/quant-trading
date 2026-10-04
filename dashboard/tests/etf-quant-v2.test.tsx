import {afterEach,expect,it} from 'vitest';
import {screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {v2ResearchSchema,v2CurrentSchema} from '@/etf-quant/v2-contracts';
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

const final={open_count:1,model_retuned:false,metrics:{signals:60,mean_rank_ic:.13,mean_spread:.05},decision:{classification:'PASS_STRONG',scientific_status:'HISTORICALLY_VALIDATED_STRONG'}};
function current(patch={}){
  return v2CurrentSchema.parse({strategy_version:'ETF_QUANT_V2',mode:'SIMULATION_ONLY',scientific_status:'HISTORICALLY_VALIDATED_STRONG',historical_classification:'PASS_STRONG',
    product_status:'HISTORICALLY_VALIDATED_RESEARCH_CANDIDATE',candidate_sha256:'a'.repeat(64),registry_sha256:'b'.repeat(64),release_sha256:'c'.repeat(64),initial_capital:'10000',
    armed:true,started:false,waiting_reason:'ARMED_NON_TRADING_DAY',epoch_count:0,signal_count:0,intent_count:0,fill_count:0,signal_date:null,top5:[],slots:[],cash_weight:1,
    next_accounting_state:'NOT_STARTED',execution_date:null,balance:'10000',cash:'10000',holdings:[],nav:[],benchmark:{identity:'CSI_300',points:[]},turnover:null,
    latest_data_date:'2026-09-30',latest_data_time:'2026-10-04T14:00:00+08:00',next_eligible_signal_date:'2026-10-08',broker_enabled:false,real_order_path:false,final_oos:final,
    mapping_summary:{model_industries:124,direct_industries:3,proxy_industries:19,executable_industry_coverage:22,unmapped_industries:102,chosen_proxy_threshold:40,latest_liquidity_date:'2026-09-30'},...patch});
}
it('version selector renders honest armed budget, coverage, scientific result and empty comparison',async()=>{
  const data=etfFixture();setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return notReachedReadiness();},
    async getV2Research(){return v2ResearchSchema.parse({...synthetic,research_status:'HISTORICALLY_VALIDATED_STRONG',revision_independently_validated:true,final_oos_opened:true,final_oos:final});},async getV2Current(){return current();}});
  await renderApp('/etf-quant/overview');await userEvent.click(screen.getByRole('button',{name:'ETF-Quant V2'}));
  expect(await screen.findByText('ETF-Quant V2 · 前向 Shadow')).toBeInTheDocument();
  expect(screen.getByText(/已布防，等待真实收盘信号/)).toBeInTheDocument();
  expect(screen.getByText(/冻结映射覆盖 22 \/ 124/)).toBeInTheDocument();
  expect(screen.getByText('V1 / V2 并行前向比较')).toBeInTheDocument();
  expect(screen.getByText('尚无前向比较观察。')).toBeInTheDocument();
});
it('failed Final OOS stays experimental and cannot claim historical validation',()=>{
  const failed=current({scientific_status:'FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT',historical_classification:'FAIL',product_status:'EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW',
    final_oos:{...final,decision:{classification:'FAIL',scientific_status:'FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT'}}});
  expect(failed.product_status).toBe('EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW');
  expect(v2CurrentSchema.safeParse({...failed,scientific_status:'HISTORICALLY_VALIDATED_STRONG'}).success).toBe(false);
  expect(v2CurrentSchema.safeParse({...current(),fill_count:1}).success).toBe(false);
});

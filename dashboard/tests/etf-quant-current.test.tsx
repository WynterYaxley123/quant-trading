import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {currentStatusSchema,snapshotSchema} from '@/etf-quant/contracts';
import {CurrentStatusPanel} from '@/etf-quant/components/CurrentStatus';
import {MappingsSection} from '@/etf-quant/sections/Mappings';
import {PortfolioSection} from '@/etf-quant/sections/Portfolio';
import {createEtfQuantApi} from '@/etf-quant/data-port';
import {etfFixture} from './etf-quant-fixtures';

function current() {return currentStatusSchema.parse({contract:'CURRENT_ETF_QUANT_STATUS_V1',project:'ETF-Quant V1',
  observed_at:'2026-10-01T01:00:00Z',mode:'SIMULATION_ONLY',read_only:true,engineering_complete:true,production_usable:true,
  factual_pipeline:'PASS',release_as_of:'2026-10-01',model_readiness:{status:'PASS',as_of:'2026-09-30',horizons:{}},
  shadow_runtime_armed:true,shadow_start_gate:'ARMED_FOR_NEXT_ELIGIBLE_T',latest_finalized_market_date:'2026-09-30',snapshot_id:'f'.repeat(64),
  calendar:{as_of_shanghai:'2026-10-01T09:00:00+08:00',today:'2026-10-01',is_trading:false,market_state:'HOLIDAY',next_eligible_trading_date:'2026-10-08'},
  runner:{status:'READY_NO_SIGNAL',observed_at:'2026-10-01T01:00:00Z',time_source:'RECEIPT',data_cutoff:'2026-09-30',
    refresh_attempted:false,reason_code:null,next_action:'RUN_ONE_SHOT_ON_NEXT_ELIGIBLE_FINALIZED_T'},
  formal:{epoch_id:null,signal_date:null,t1_status:null,epoch_count:0,signal_count:0,intent_count:0,fill_count:0,holdings_count:0,
    cash_weight:null,risk_asset_weight:null,nav:null,pnl:null},
  provenance:{code_sha:'c'.repeat(40),release_code_sha:'c'.repeat(40),candidate_hash:'a'.repeat(64),pit_registry_hash:'b'.repeat(64),strict_registry_hash:'d'.repeat(64),cnequity_pin:'e'.repeat(40)},
  evidence:{production_pit:'PASS',strict_registry:'PASS',sws:'PASS_WITH_KNOWN_LIMITATION',known_limitation:'SYNTHETIC_TEST_ONLY'},
  historical_status:null,one_shot_command:'SYNTHETIC_COMMAND_NOT_EXECUTABLE',broker_enabled:false,real_order_path:false});}
describe('current operations console',()=>{
  it('renders armed zero-epoch state, usability, cutoff and dynamic next session',()=>{
    render(<CurrentStatusPanel data={current()} />);
    expect(screen.getByText('TRUE')).toBeInTheDocument();expect(screen.getByText('ARMED')).toBeInTheDocument();
    expect(screen.getByText('2026-09-30')).toBeInTheDocument();expect(screen.getByText('2026-10-08')).toBeInTheDocument();
    expect(screen.getByText(/No Formal Shadow Epoch yet/)).toBeInTheDocument();
    expect(screen.getByText('OFF / OFF')).toBeInTheDocument();expect(screen.queryByRole('button',{name:/BUY|SELL|Live|Broker/})).not.toBeInTheDocument();
  });
  it('renders a started fixture without pretending T1 fill already exists',()=>{
    const data=current();data.shadow_start_gate='STARTED';data.formal={...data.formal,epoch_id:'SYNTHETIC_EPOCH',epoch_count:1,
      signal_count:1,signal_date:'2026-10-08',t1_status:'AWAITING_T1_OPEN'};
    render(<CurrentStatusPanel data={data} />);expect(screen.getByText('STARTED')).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC_EPOCH')).toBeInTheDocument();expect(screen.getByText(/AWAITING_T1_OPEN/)).toBeInTheDocument();
    expect(screen.queryByText(/No Formal Shadow Epoch yet/)).not.toBeInTheDocument();
  });
  it('labels historical superseded failures independently from current gate',()=>{
    const data=current();data.historical_status={status:'SUPERSEDED / HISTORICAL',reason_code:'MODEL_WARMUP_INCOMPLETE',processed_at:'2026-09-30T12:00:00Z'};
    render(<CurrentStatusPanel data={data} />);expect(screen.getByText(/SUPERSEDED \/ HISTORICAL/)).toBeInTheDocument();
    expect(screen.getByText('ARMED_FOR_NEXT_ELIGIBLE_T')).toBeInTheDocument();
  });
  it('does not hardcode production usability',()=>{
    const data=current();data.production_usable=false;render(<CurrentStatusPanel data={data} />);expect(screen.getByText('FALSE')).toBeInTheDocument();
  });
  it('rejects broker enabled and real-order DTOs',()=>{
    expect(()=>currentStatusSchema.parse({...current(),broker_enabled:true})).toThrow();
    expect(()=>currentStatusSchema.parse({...current(),real_order_path:true})).toThrow();
  });
  it('loads current status only through GET with credentials omitted',async()=>{
    const transport=async(input:RequestInfo|URL,init?:RequestInit)=>{
      expect(String(input)).toContain('/current');expect(init?.method).toBe('GET');expect(init?.credentials).toBe('omit');
      return new Response(JSON.stringify({schemaVersion:'1.0.0',error:null,data:current(),meta:{runId:null,manifestSha256:null,etfQuant:true}}));
    };
    expect((await createEtfQuantApi('http://127.0.0.1:3312',transport).getCurrentStatus!()).production_usable).toBe(true);
  });
  it('renders Cash, Strict and Proxy slots with rank, weights and evidence',()=>{
    const d=etfFixture();d.status.execution_policy='B40_WITH_CASH';d.strategy.execution_policy='B40_WITH_CASH';
    d.strategy.rebalance='EXECUTABLE_MEMBER_SET_CHANGE_INCLUDING_EXECUTABILITY_V1';d.strategy.cash_semantics='UNALLOCATED_EXECUTION_CAPACITY';
    const slots=Array.from({length:5},(_,i)=>({industry_code:`370${i+1}`,industry_name:null,industry_rank:i+1,score:5-i,
      mapping_type:(i===4?'CASH_UNEXECUTABLE_SIGNAL':i===0?'STRICT_MAPPING':'PROXY_EXPOSURE') as 'CASH_UNEXECUTABLE_SIGNAL'|'STRICT_MAPPING'|'PROXY_EXPOSURE',
      etf_code:i===4?null:`51000${i}.SH`,etf_name:null,target_l2_exposure:i===4?null:.5,target_is_largest_l2:i===4?null:true,
      liquidity_status:null,mean_amount_cny:null,target_weight:.2,cash_retained_weight:i===4?.2:0,
      evidence_available_at:'2026-09-30T12:00:00Z',execution_reason:i===4?'NO_ORDER_UNEXECUTABLE_SIGNAL':'SYNTHETIC'}));
    d.mappings={...d.mappings,status:'READY',slots,entries:slots.slice(0,4),cash_weight:.2,risk_asset_weight:.8};
    render(<MappingsSection data={snapshotSchema.parse(d)} />);expect(screen.getByText('CASH / FAIL-CLOSED')).toBeInTheDocument();
    expect(screen.getByText('STRICT_MAPPING')).toBeInTheDocument();expect(screen.getAllByText('PROXY_EXPOSURE')).toHaveLength(3);
    expect(screen.getByRole('columnheader',{name:/^Rank/})).toBeInTheDocument();
    expect(screen.getByRole('columnheader',{name:/^Evidence available at/})).toBeInTheDocument();
  });
  it('distinguishes Formal T0 epoch from the absent T1 account',()=>{
    const d=etfFixture();d.status.shadow_epoch={epoch_id:'SYNTHETIC_EPOCH',created_at:'2026-10-08T12:00:00Z'};
    d.status.formal_signal={signal_date:'2026-10-08',t1_status:'AWAITING_T1_OPEN'};
    render(<PortfolioSection data={d} />);expect(screen.getByText('Formal Shadow Epoch 已创建')).toBeInTheDocument();
    expect(screen.getByText(/AWAITING_T1_OPEN/)).toBeInTheDocument();
  });
});

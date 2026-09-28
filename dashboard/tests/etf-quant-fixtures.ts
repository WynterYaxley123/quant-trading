import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { readinessSchema, snapshotSchema, type EtfQuantReadiness, type EtfQuantSnapshot } from '@/etf-quant/contracts';

// Entirely SYNTHETIC unit-test DTOs; never copied to real runtime or API defaults.
export function etfFixture():EtfQuantSnapshot {
  const strategy=JSON.parse(readFileSync(resolve(process.cwd(),'../services/etf-quant-api/strategy.json'),'utf8'));
  const rankings=Array.from({length:25},(_,i)=>({rank:i+1,industry_code:`801${String(i).padStart(3,'0')}`,score:25-i}));
  return snapshotSchema.parse({
    status:{product:'ETF_QUANT',version:'ETF_QUANT_V1',mode:'SIMULATION_ONLY',phase:'MAPPING_ADMISSION_BLOCKED',reason:'NO_VERIFIED_EVIDENCE',
      snapshot_id:'a'.repeat(64),source_commit:'b'.repeat(40),source_version:'SYNTHETIC_TEST_ONLY',code_commit:'c'.repeat(40),
      cutoff:'2026-09-24',updated_at:'2026-09-24T18:00:00+08:00',signal_date:'2026-09-24',execution_date:null,epoch:null,
      mapping_hash:'d'.repeat(64),strategy_hash:'e'.repeat(64),broker_enabled:false,real_order_path:false,validation_opened:false,final_oos_read:false},
    strategy,models:[],rankings:{'10d':rankings,'40d':rankings,'120d':rankings,fusion:rankings},
    portfolio_summary:{status:'NOT_STARTED',cash:null,market_value:null,total_equity:null,initial_cash:'10000',realized_pnl:null,
      unrealized_pnl:null,total_return:null,total_pnl:null,daily_return:null,turnover:null,
      turnover_definition:'CUMULATIVE_ABSOLUTE_SLIPPED_NOTIONAL_DIVIDED_BY_INITIAL_CASH',
      max_drawdown:null,sharpe:null,rebalance_count:null,last_rebalance_at:null},
    holdings:[],nav:[],trades:[],mappings:{status:'MAPPING_ADMISSION_BLOCKED',reason:'NO_VERIFIED_EVIDENCE',entries:[],diagnostics:[]},
    benchmark:{symbol:'000300.SH',status:'NOT_STARTED',points:[],nasdaq:'DEFERRED',sp500:'DEFERRED',model_input:false},
    health:{status:'MAPPING_ADMISSION_BLOCKED',blockers:['NO_VERIFIED_EVIDENCE'],quality_flags:['HISTORICAL_MEMBERSHIP_PIT_UNPROVEN'],
      adjustment_exact_rows:100,adjustment_rejected_rows:0,coverage:[],strict_tls:'STRICT_TEST',historical_performance:false},
  });
}

export function runningFixture():EtfQuantSnapshot {
  const data=etfFixture();
  const at='2026-09-24T18:00:00+08:00';
  data.status.phase='RUNNING';data.status.reason=null;
  data.status.epoch={epoch_id:'SYNTHETIC_EPOCH_TEST_ONLY',started_at:at,market_cutoff:'2026-09-24',provider_snapshot_id:'a'.repeat(64),
    mapping_hash:'d'.repeat(64),strategy_config_hash:'e'.repeat(64),initial_cash:'10000',code_commit:'c'.repeat(40),bookkeeping:'DELAYED_EOD_ACTUAL_PROCESSED_AT'};
  data.portfolio_summary={...data.portfolio_summary,status:'RUNNING',cash:'9000',market_value:'1000',total_equity:'10000',realized_pnl:'0',
    unrealized_pnl:'0',total_pnl:'0',total_return:0,max_drawdown:0,turnover:.1,rebalance_count:1,last_rebalance_at:at};
  data.holdings=[{asset_id:'510000.SH',etf_name:'SYNTHETIC ETF TEST ONLY',industry_code:'801000',industry_name:'SYNTHETIC INDUSTRY',quantity:'100',
    average_cost:'10',mark_price:'10',market_value:'1000',weight:.1,unrealized_pnl:'0',unrealized_return:0}];
  data.nav=[{timestamp:at,cash:'9000',market_value:'1000',total_equity:'10000',realized_pnl:'0',unrealized_pnl:'0',normalized_nav:'1',trade_date:'2026-09-24',processed_at:at}];
  data.benchmark.status='RUNNING';data.benchmark.points=[{trade_date:'2026-09-24',normalized:1,close:3000,snapshot_id:'a'.repeat(64)}];
  return snapshotSchema.parse(data);
}
export function trainedFixture():EtfQuantSnapshot {
  const data=etfFixture();
  data.models=[10,40,120].map(h=>{
    const names=h===10?data.strategy.h10_factors:h===40?data.strategy.h40_factors:data.strategy.h120_factors;
    return {horizon:h as 10|40|120,factor_names:names,alpha:.01,coefficients:names.map((_,i)=>(i%2?1:-1)*.01*(i+1)),intercept:.001,
      training:{window_start:'2025-09-01',label_cutoff:'2026-03-01',training_start:'2025-09-01',training_end:'2026-03-01',training_day_count:60,sample_count:1500},
      current_snapshot_observed_at:'2026-09-24T17:00:00+08:00',available_at:null,source_published_at:null,
      quality_flag:'HISTORICAL_MEMBERSHIP_PIT_UNPROVEN',model_hash:'f'.repeat(64)};
  });
  return snapshotSchema.parse(data);
}

// 默认：后台尚未发布 readiness artifact → 整体 NOT_REACHED、无门控记录。
export function notReachedReadiness():EtfQuantReadiness {
  return readinessSchema.parse({contract:'SHADOW_START_READINESS_V1',generated_at:null,data_cutoff:null,
    overall:'NOT_REACHED',gates:[],shadow_epoch_created:false,shadow_started:false,notes:[]});
}

// 合成门控清单：覆盖 PASS / BLOCKED / DEFERRED / NOT_REACHED 四种状态。
export function gatesReadinessFixture():EtfQuantReadiness {
  return readinessSchema.parse({contract:'SHADOW_START_READINESS_V1',generated_at:'2026-09-24T18:05:00+08:00',data_cutoff:'2026-09-24',
    overall:'BLOCKED',shadow_epoch_created:false,shadow_started:false,
    gates:[
      {name:'DATA_FRESHNESS',status:'PASS',summary:'数据截止日满足新鲜度要求。',evidence:'cutoff=2026-09-24'},
      {name:'MAPPING_ADMISSION',status:'BLOCKED',summary:'映射准入被阻断，缺少已验证证据。',evidence:'NO_VERIFIED_EVIDENCE'},
      {name:'OVERSEAS_BENCHMARK',status:'DEFERRED',summary:'海外基准暂缓接入，不影响启动评估。',evidence:null},
      {name:'MODEL_WARMUP',status:'NOT_REACHED',summary:'模型预热评估尚未执行。',evidence:null},
    ],
    notes:['SYNTHETIC TEST ONLY：全部内容均为合成测试数据。']});
}

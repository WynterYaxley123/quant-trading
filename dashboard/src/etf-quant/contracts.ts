import { z } from 'zod';

const nullableText = z.string().nullable();
const money = z.string().regex(/^-?\d+(\.\d+)?$/);
const optionalMoney = money.nullable();
const numeric = z.number().finite();
const H10=['d10','p5','align','vc','dd20'] as const;
const HLONG=['d5','d10','d20','d60','d120','p5','p10','p20','p60','p120','align','v5','v20','vc','rev5','rev10','dd20','dd60','rsi'] as const;
const namedFactors=(names:readonly string[])=>z.array(z.string()).refine(v=>JSON.stringify(v)===JSON.stringify(names));
const rank = z.object({rank:z.number().int().positive(),industry_code:z.string(),score:numeric});
const epoch = z.object({epoch_id:z.string(),started_at:z.string(),market_cutoff:z.string(),provider_snapshot_id:z.string(),
  mapping_hash:z.string(),strategy_config_hash:z.string(),initial_cash:z.literal('10000'),code_commit:z.string(),bookkeeping:z.string()});
export const statusSchema = z.object({product:z.literal('ETF_QUANT'),version:z.literal('ETF_QUANT_V1'),mode:z.literal('SIMULATION_ONLY'),
  phase:z.string(),reason:nullableText,snapshot_id:nullableText,source_commit:nullableText,source_version:nullableText,
  code_commit:nullableText,cutoff:nullableText,updated_at:nullableText,signal_date:nullableText,execution_date:nullableText,
  epoch:epoch.nullable(),mapping_hash:nullableText,strategy_hash:nullableText,broker_enabled:z.literal(false),
  real_order_path:z.literal(false),validation_opened:z.literal(false),final_oos_read:z.literal(false),
  industry_level:z.literal('SHENWAN_L2').optional()});
export const strategySchema = z.object({version:z.literal('ETF_QUANT_V1'),mode:z.literal('SIMULATION_ONLY'),
  currency:z.literal('CNY'),initial_cash:z.literal('10000'),model:z.literal('Ridge'),alpha:z.literal(.01),
  training_window_months:z.literal(6),minimum_training_days:z.literal(30),window_anchor:z.literal('PER_HORIZON_LABEL_CUTOFF'),
  target:z.literal('SAME_DATE_CROSS_SECTIONAL_EXCESS_FORWARD_RETURN'),preprocessing:z.literal('NONE_RAW_X'),
  horizons:z.tuple([z.literal(10),z.literal(40),z.literal(120)]),h10_factors:namedFactors(H10),
  h40_factors:namedFactors(HLONG),h120_factors:namedFactors(HLONG),
  fusion:z.object({'10':z.literal(.25),'40':z.literal(.5),'120':z.literal(.25)}),zscore_ddof:z.literal(0),
  top_k:z.literal(5),target_weight_cap:z.literal(.35),weighting:z.string(),rebalance:z.literal('EXECUTABLE_ETF_SET_CHANGE_ONLY'),
  execution:z.string(),bookkeeping:z.literal('DELAYED_EOD_ACTUAL_PROCESSED_AT'),lot_size:z.number().int().positive(),
  costs:z.object({commission_bps:money,slippage_bps:money,stamp_duty_bps:money,minimum_commission:money}),
  broker_enabled:z.literal(false),real_order_path:z.literal(false),source_c_identity:z.literal('INTERNAL_SHENWAN_INDUSTRY_SERIES_V1'),
  construction:z.literal('INTERNAL_EQUAL_WEIGHT_SHENWAN_SERIES_V1'),pit_quality:z.literal('HISTORICAL_MEMBERSHIP_PIT_UNPROVEN'),
  industry_level:z.literal('SHENWAN_L2'),industry_level_width:z.literal(4),
  taxonomy_identity:z.literal('SHENWAN_INDUSTRY_TAXONOMY_2021_V1'),
  liquidity_rule:z.literal('TWENTY_SESSION_REQUIRED_AMOUNT_NO_SUBSTITUTION'),liquidity_sessions:z.literal(20),
  available_at:z.null(),source_published_at:z.null(),
  factor_registry:z.array(z.object({name:z.string(),formula:z.string(),lookback_sessions:z.number().int().positive(),input_fields:z.array(z.string())})).length(19)}).passthrough();
const model = z.object({horizon:z.union([z.literal(10),z.literal(40),z.literal(120)]),factor_names:z.array(z.string()),alpha:z.literal(.01),
  coefficients:z.array(numeric),intercept:numeric,training:z.object({window_start:z.string(),label_cutoff:z.string(),training_start:z.string(),
    training_end:z.string(),training_day_count:z.number().int(),sample_count:z.number().int()}).passthrough(),
  current_snapshot_observed_at:z.string(),available_at:z.null(),source_published_at:z.null(),quality_flag:z.string(),model_hash:z.string()})
  .refine(v=>v.coefficients.length === v.factor_names.length
    && JSON.stringify(v.factor_names)===JSON.stringify(v.horizon===10?H10:HLONG)
    && v.training.training_day_count>=30 && v.training.training_end<=v.training.label_cutoff);
const summary = z.object({status:z.string(),cash:optionalMoney,market_value:optionalMoney,total_equity:optionalMoney,initial_cash:z.literal('10000'),
  realized_pnl:optionalMoney,unrealized_pnl:optionalMoney,total_return:numeric.nullable(),max_drawdown:numeric.nullable(),sharpe:numeric.nullable(),
  rebalance_count:z.number().int().nonnegative().nullable(),last_rebalance_at:nullableText});
const completeSummary=summary.extend({total_pnl:optionalMoney,daily_return:numeric.nullable(),turnover:numeric.nonnegative().nullable(),
  turnover_definition:z.literal('CUMULATIVE_ABSOLUTE_SLIPPED_NOTIONAL_DIVIDED_BY_INITIAL_CASH')});
const holding = z.object({asset_id:z.string(),quantity:money,average_cost:money,mark_price:money,market_value:money,weight:numeric,unrealized_pnl:money});
const completeHolding=holding.extend({etf_name:z.string(),industry_code:z.string(),industry_name:z.string(),unrealized_return:numeric});
const nav = z.object({timestamp:z.string(),cash:money,market_value:money,total_equity:money,realized_pnl:money,unrealized_pnl:money,
  normalized_nav:money,trade_date:z.string(),processed_at:z.string()});
const trade = z.object({fill_id:z.string(),intent:z.object({intent_id:z.string(),asset_id:z.string(),side:z.enum(['BUY','SELL']),quantity:money,
  signal_session:z.string(),execution_session:z.string(),mode:z.literal('SIMULATION_ONLY')}).passthrough(),
  executed_at:z.string(),reference_open:money,price:money,commission:money,slippage:money,stamp_duty:money,
  processed_at:z.string(),market_execution_at:z.string(),intent_persisted_at:z.string(),execution_price_source:z.string(),accounting_mode:z.string(),
  provider_snapshot_id:z.string(),total_cash_impact:money,rebalance_reason:z.enum(['INITIAL_BUILD','EXECUTABLE_ETF_SET_CHANGED'])});
const mapping = z.object({status:z.string(),reason:nullableText,
  industry_level:z.literal('SHENWAN_L2').optional(),liquidity_sessions:z.literal(20).optional(),
  liquidity_window:z.array(z.string()).optional(),
  entries:z.array(z.object({industry_code:z.string(),industry_name:z.string(),etf_code:z.string(),etf_name:z.string(),
    verification_status:z.string(),mapping_method:z.string(),classification:z.string(),effective_from:z.string(),effective_to:nullableText,
    tracking_index_code:z.string(),tracking_index_name:z.string(),mean_amount_cny:numeric}).passthrough()),
  diagnostics:z.array(z.object({industry_code:z.string(),etf_code:z.string(),reason:nullableText,verification_status:z.string(),
    liquidity_sessions:z.number().int(),mean_amount_cny:numeric.nullable(),
    industry_level:z.literal('SHENWAN_L2').optional(),liquidity_window:z.array(z.string()).optional()}).passthrough())});
const benchmark = z.object({symbol:z.literal('000300.SH'),status:z.string(),points:z.array(z.object({trade_date:z.string(),normalized:numeric,close:numeric,snapshot_id:z.string()})),
  nasdaq:z.literal('DEFERRED'),sp500:z.literal('DEFERRED'),model_input:z.literal(false)});
const health = z.object({status:z.string(),blockers:z.array(z.string()),quality_flags:z.array(z.string()),
  adjustment_exact_rows:z.number().int().nonnegative().nullable(),adjustment_rejected_rows:z.number().int().nonnegative().nullable(),
  coverage:z.array(z.object({industry_code:z.string(),trade_date:z.string(),status:z.string(),eligible_members:z.number().int(),
    valid_constituents:z.number().int(),coverage:numeric,reason:nullableText}).passthrough()).nullable(),strict_tls:z.string(),historical_performance:z.literal(false)}).passthrough();

export const snapshotSchema = z.object({status:statusSchema,strategy:strategySchema,models:z.array(model),
  rankings:z.object({'10d':z.array(rank),'40d':z.array(rank),'120d':z.array(rank),fusion:z.array(rank)}),
  portfolio_summary:completeSummary,holdings:z.array(completeHolding),nav:z.array(nav),trades:z.array(trade),mappings:mapping,benchmark,health})
  .refine(v=>v.status.epoch !== null || (v.nav.length===0 && v.holdings.length===0 && v.trades.length===0
    && v.benchmark.points.length===0 && ['cash','market_value','total_equity','realized_pnl','unrealized_pnl','total_return',
      'total_pnl','daily_return','turnover','max_drawdown','sharpe','rebalance_count'].every(k=>v.portfolio_summary[k as keyof typeof v.portfolio_summary]===null)), 'No fabricated pre-epoch results')
  .refine(v=>!v.status.epoch || v.nav.every(p=>Date.parse(p.timestamp)>=Date.parse(v.status.epoch!.started_at)
    && p.trade_date>=v.status.epoch!.market_cutoff), 'No pre-epoch NAV')
  .refine(v=>!v.status.epoch || v.holdings.every(p=>Number(p.quantity)>0 && Number(p.quantity)%v.strategy.lot_size===0), 'No fractional/short holdings');
const gateStatus = z.enum(['PASS','BLOCKED','NOT_REACHED','DEFERRED','UNKNOWN']);
export const readinessSchema = z.object({contract:z.literal('SHADOW_START_READINESS_V1'),generated_at:nullableText,
  data_cutoff:nullableText,overall:z.enum(['PASS','BLOCKED','NOT_REACHED']),
  gates:z.array(z.object({name:z.string(),status:gateStatus,summary:z.string(),evidence:nullableText})).max(64),
  shadow_epoch_created:z.literal(false),shadow_started:z.literal(false),notes:z.array(z.string()).max(64)});
export type EtfQuantReadiness = z.infer<typeof readinessSchema>;
export type EtfQuantSnapshot = z.infer<typeof snapshotSchema>;
export type EtfQuantStatus = z.infer<typeof statusSchema>;
export const endpointSchemas = {'status':statusSchema,'strategy':strategySchema,'models':z.array(model),
  'rankings/10d':z.array(rank),'rankings/40d':z.array(rank),'rankings/120d':z.array(rank),'rankings/fusion':z.array(rank),
  'portfolio/summary':completeSummary,'portfolio/holdings':z.array(completeHolding),'portfolio/nav':z.array(nav),'trades':z.array(trade),
  'mappings':mapping,'benchmark/csi300':benchmark,'health':health} as const;
export type EtfEndpoint = keyof typeof endpointSchemas;
export const envelopeSchema = z.object({schemaVersion:z.literal('1.0.0'),data:z.unknown(),error:z.null(),
  meta:z.object({runId:nullableText,manifestSha256:nullableText,attemptRunId:nullableText.optional(),
    attemptManifestSha256:nullableText.optional(),etfQuant:z.literal(true)})});

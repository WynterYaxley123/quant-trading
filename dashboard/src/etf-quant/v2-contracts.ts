import { z } from 'zod';

const metrics = z.object({ signals: z.number().int().nonnegative(), mean_rank_ic: z.number().finite(), mean_spread: z.number().finite() });
export const v2ResearchSchema = z.object({
  product: z.literal('ETF_QUANT_V2'), research_status: z.enum(['VALIDATION_INFORMED_NOT_INDEPENDENTLY_VALIDATED','PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE','FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT']),
  candidate_sha256: z.string().regex(/^[a-f0-9]{64}$/), evidence_mode: z.enum(['HIGH_CONFIDENCE','EXTENDED_HISTORY']),
  specification: z.object({identifier: z.string(), family: z.string(), horizons: z.array(z.number().int().positive()),
    fusion: z.array(z.number().positive()), alpha: z.number().positive(), training_months: z.number().int().positive(),
    scaling: z.enum(['RAW','TRAIN_ONLY_STANDARDIZED']), factors: z.array(z.string()).length(19), h10_factors: z.array(z.string()).length(5)}),
  historical_start: z.string(), historical_end: z.string(), trading_sessions: z.number().int().positive(), history_years: z.number().positive(),
  membership_tier_rows: z.object({A:z.number().int().nonnegative(),B:z.number().int().nonnegative(),C:z.number().int().nonnegative(),D:z.number().int().nonnegative()}),
  development: metrics, validation_status: z.literal('FAILED'), validation: metrics,
  revision_independently_validated: z.boolean(), final_oos_opened: z.boolean(), shadow_ready: z.literal(true), shadow_started: z.literal(false),
  epoch_count: z.literal(0), signal_count: z.literal(0), intent_count: z.literal(0), fill_count: z.literal(0),
  broker_enabled: z.literal(false), real_order_path: z.literal(false), limitations: z.array(z.string()),
  final_oos:z.object({open_count:z.literal(1),model_retuned:z.literal(false),metrics,
    decision:z.object({classification:z.enum(['PASS_STRONG','PASS_WEAK','FAIL']),scientific_status:z.string()})}).optional(),
}).superRefine((v,ctx)=>{
  if(v.specification.horizons.length!==v.specification.fusion.length || Math.abs(v.specification.fusion.reduce((a,b)=>a+b,0)-1)>1e-9)
    ctx.addIssue({code:z.ZodIssueCode.custom,message:'Invalid frozen fusion'});
  if(v.final_oos_opened!==Boolean(v.final_oos) || v.revision_independently_validated)
    ctx.addIssue({code:z.ZodIssueCode.custom,message:'Final OOS authorization/result mismatch'});
});
export type V2Research = z.infer<typeof v2ResearchSchema>;

const scientific=z.enum(['PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE','FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT']);
const money=z.string().regex(/^\d+(?:\.\d+)?$/);
export const v2CurrentSchema=z.object({
  strategy_version:z.literal('ETF_QUANT_V2'),mode:z.literal('SIMULATION_ONLY'),scientific_status:scientific,
  historical_classification:z.enum(['PASS_STRONG','PASS_WEAK','FAIL']),product_status:z.enum(['PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE','EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW']),
  candidate_sha256:z.string().regex(/^[a-f0-9]{64}$/),registry_sha256:z.string().regex(/^[a-f0-9]{64}$/),release_sha256:z.string().regex(/^[a-f0-9]{64}$/),
  initial_capital:z.literal('10000'),armed:z.boolean(),started:z.boolean(),waiting_reason:z.string().nullable(),
  epoch_count:z.number().int().nonnegative(),signal_count:z.number().int().nonnegative(),intent_count:z.number().int().nonnegative(),fill_count:z.number().int().nonnegative(),
  signal_date:z.string().nullable(),top5:z.array(z.tuple([z.string(),z.number().finite()])),
  slots:z.array(z.object({l2_code:z.string(),l2_name:z.string().nullable().optional(),etf_code:z.string().nullable(),weight:z.number().min(0).max(0.35),
    mapping_class:z.enum(['DIRECT_INDUSTRY_TRACKER','VERIFIED_INDUSTRY_PROXY','NO_RELIABLE_MAPPING']),confidence:z.string().nullable(),evidence_date:z.string().nullable()})),
  cash_weight:z.number().min(0).max(1),next_accounting_state:z.string(),execution_date:z.string().nullable(),balance:money,cash:money,
  holdings:z.array(z.object({asset_id:z.string(),quantity:money,average_cost:money,mark_price:money})),
  nav:z.array(z.object({date:z.string(),equity:money,normalized_nav:z.number().positive()})),
  benchmark:z.object({identity:z.literal('CSI_300'),points:z.array(z.object({date:z.string(),normalized_nav:z.number().positive()}))}),
  turnover:z.number().finite().nonnegative().nullable(),latest_data_date:z.string().nullable(),latest_data_time:z.string().nullable(),next_eligible_signal_date:z.string().nullable().optional(),
  broker_enabled:z.literal(false),real_order_path:z.literal(false),
  final_oos:z.object({open_count:z.literal(1),model_retuned:z.literal(false),metrics,decision:z.object({classification:z.enum(['PASS_STRONG','PASS_WEAK','FAIL']),scientific_status:z.string()})}),
  mapping_summary:z.object({model_industries:z.literal(124),direct_industries:z.number().int().nonnegative(),proxy_industries:z.number().int().nonnegative(),executable_industry_coverage:z.number().int().nonnegative(),unmapped_industries:z.number().int().nonnegative(),chosen_proxy_threshold:z.literal(40),latest_liquidity_date:z.string()}),
}).superRefine((v,ctx)=>{
  const statuses={PASS_STRONG:'PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE',PASS_WEAK:'PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE',FAIL:'FINAL_OOS_FAILED_FORWARD_SHADOW_EXPERIMENT'};
  if(v.scientific_status!==statuses[v.historical_classification] || v.final_oos.decision.classification!==v.historical_classification
    || (v.historical_classification==='FAIL')!==(v.product_status==='EXPERIMENTAL_UNVALIDATED_RESEARCH_SHADOW'))ctx.addIssue({code:z.ZodIssueCode.custom,message:'Scientific status mismatch'});
  if(!v.started && (v.epoch_count!==0 || v.signal_count!==0 || v.intent_count!==0 || v.fill_count!==0 || v.nav.length))ctx.addIssue({code:z.ZodIssueCode.custom,message:'Unstarted ledger must be empty'});
});
export type V2Current=z.infer<typeof v2CurrentSchema>;

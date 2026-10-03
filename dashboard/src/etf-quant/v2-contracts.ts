import { z } from 'zod';

const metrics = z.object({ signals: z.number().int().nonnegative(), mean_rank_ic: z.number().finite(), mean_spread: z.number().finite() });
export const v2ResearchSchema = z.object({
  product: z.literal('ETF_QUANT_V2'), research_status: z.literal('VALIDATION_INFORMED_NOT_INDEPENDENTLY_VALIDATED'),
  candidate_sha256: z.string().regex(/^[a-f0-9]{64}$/), evidence_mode: z.enum(['HIGH_CONFIDENCE','EXTENDED_HISTORY']),
  specification: z.object({identifier: z.string(), family: z.string(), horizons: z.array(z.number().int().positive()),
    fusion: z.array(z.number().positive()), alpha: z.number().positive(), training_months: z.number().int().positive(),
    scaling: z.enum(['RAW','TRAIN_ONLY_STANDARDIZED']), factors: z.array(z.string()).length(19), h10_factors: z.array(z.string()).length(5)}),
  historical_start: z.string(), historical_end: z.string(), trading_sessions: z.number().int().positive(), history_years: z.number().positive(),
  membership_tier_rows: z.object({A:z.number().int().nonnegative(),B:z.number().int().nonnegative(),C:z.number().int().nonnegative(),D:z.number().int().nonnegative()}),
  development: metrics, validation_status: z.literal('FAILED'), validation: metrics,
  revision_independently_validated: z.literal(false), final_oos_opened: z.literal(false), shadow_ready: z.literal(true), shadow_started: z.literal(false),
  epoch_count: z.literal(0), signal_count: z.literal(0), intent_count: z.literal(0), fill_count: z.literal(0),
  broker_enabled: z.literal(false), real_order_path: z.literal(false), limitations: z.array(z.string()),
}).superRefine((v,ctx)=>{
  if(v.specification.horizons.length!==v.specification.fusion.length || Math.abs(v.specification.fusion.reduce((a,b)=>a+b,0)-1)>1e-9)
    ctx.addIssue({code:z.ZodIssueCode.custom,message:'Invalid frozen fusion'});
});
export type V2Research = z.infer<typeof v2ResearchSchema>;

import { z } from 'zod';
import { industryForecastBaseUrl } from '@/lib/env';

const finite=z.number().finite();
const hash=z.string().regex(/^[a-f0-9]{64}$/);
const day=z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const stats=z.object({count:z.number().int().nonnegative(),mean:finite.nullable(),median:finite.nullable(),minimum:finite.nullable(),maximum:finite.nullable(),std:finite.nullable(),positive_fraction:finite.min(0).max(1).nullable()}).strict();
const metric=z.object({rank_ic:stats,signal_count:z.number().int().nonnegative(),calendar_blocks:z.array(z.object({block:z.number().int().min(1).max(4),signals:z.number().int().nonnegative(),rank_ic:stats,spread:stats}).strict()).length(4),raw_spread:stats}).strict();
export const rev10OverviewSchema=z.object({
  model:z.object({display_name:z.literal('SWL1 REV10 Short-V1'),model_name:z.literal('SWL1_REV10_SHORT_V1'),model_type:z.literal('FIXED_RULE'),training_required:z.literal(false),lookback:z.literal(10),universe_count:z.literal(30),primary_horizon:z.literal(10),secondary_horizon:z.literal(5),source:z.literal('CNEquity'),source_commit:z.literal('1650e384a3fd1f67a70144a489acc91432f1df27'),primary_series:z.literal('RECONSTRUCTED_SWL1_EQUAL_WEIGHT'),historical_cutoff:z.literal('2026-09-29')}).passthrough(),
  model_hash:hash,classification:z.literal('EXPLORATORY_POST_HOC'),historical_cutoff:z.literal('2026-09-29'),
  models:z.record(z.enum(['S0','S1','S2','S3','S4']),z.object({'5':metric,'10':metric}).strict()),
  decision:z.enum(['A','B','C','D']),limitations:z.array(z.string()),
  readiness:z.object({model_implemented:z.literal(true),historical_exploration_available:z.literal(true),preregistration_draft_ready:z.literal(true),formal_preregistration_active:z.literal(false),production_source_admitted:z.literal(false),production_signature_authority:z.literal('SIGNATURE_AUTHORITY_NOT_ESTABLISHED'),statistical_design:z.literal('STATISTICAL_DESIGN_PENDING'),prospective_observations_collected:z.literal(0),independent_validation_complete:z.literal(false),data_status:z.literal('DATA_SOURCE_NOT_READY'),real_sources_admitted:z.literal(0),historical_access_isolation:z.literal('NOT_CERTIFIED'),certified_historically_unseen_sessions:z.literal(0),swl1_v1:z.literal('FAILED_VALIDATION'),swl1_v2:z.literal('FAILED_VALIDATION'),final_oos_opened:z.literal(false)}).strict(),
  charts:z.array(z.object({id:z.enum(['signal-rankic','temporal-blocks','ridge-comparison','factor-target-correlations','industry-sensitivity','concentration-turnover']),title:z.string()}).strict()).length(6),
  evidence:z.array(z.object({id:z.enum(['design','chinese-report','acceptance','data-boundary','research-decision','source-qualification','preregistration-draft']),reference:z.string()}).strict()).length(7),
  research_pr:z.literal('https://github.com/WynterYaxley123/quant-trading/pull/36'),source_hashes:z.object({summary:hash,boundary:hash}).strict(),
}).strict();
const row=z.object({rank:z.number().int().min(1).max(30),industry_code:z.string().regex(/^\d{6}$/),industry_name:z.string().min(1),name_verified:z.boolean(),rev10_score:finite,relative_score:finite,trailing_mean_return:finite,data_asof:day,data_completeness:z.literal('10_OF_10_FINITE_SESSIONS'),source_generation:z.string().min(1)}).strict();
const ranking=z.object({
  status:z.literal('HISTORICAL_REPLAY'),namespace:z.literal('RESEARCH_REPLAY_ONLY'),asof:day,count:z.literal(30),complete_universe:z.literal(true),ranking_basis:z.literal('REV10_DESCENDING_CODE_ASCENDING_TIES'),
  rows:z.array(row).length(30),top5:z.array(row).length(5),bottom5:z.array(row).length(5),manifest_sha256:hash,source_commit:z.string().regex(/^[a-f0-9]{40}$/),source_generation:z.string(),window_sessions:z.array(day).length(10),
}).strict().superRefine((v,ctx)=>{
  const sorted=[...v.rows].sort((a,b)=>b.rev10_score-a.rev10_score||a.industry_code.localeCompare(b.industry_code));
  const bottom=[...v.rows].sort((a,b)=>a.rev10_score-b.rev10_score||a.industry_code.localeCompare(b.industry_code)).slice(0,5);
  if(v.asof>'2026-09-29'||new Set(v.rows.map(r=>r.industry_code)).size!==30||v.rows.some((r,i)=>r.rank!==i+1||r.data_asof!==v.asof)||JSON.stringify(sorted)!==JSON.stringify(v.rows)||JSON.stringify(v.top5)!==JSON.stringify(v.rows.slice(0,5))||JSON.stringify(v.bottom5)!==JSON.stringify(bottom)||v.window_sessions.at(-1)!==v.asof)ctx.addIssue({code:'custom',message:'PRIVATE_RANKING_CONSISTENCY_REQUIRED'});
});
export const rev10RankingSchema=z.union([ranking,z.object({status:z.literal('UNAVAILABLE'),reason:z.string(),asof:z.null(),count:z.literal(0),rows:z.array(z.never()).length(0),top5:z.array(z.never()).length(0),bottom5:z.array(z.never()).length(0)}).strict()]);
export type Rev10Overview=z.infer<typeof rev10OverviewSchema>;
export type Rev10Ranking=z.infer<typeof rev10RankingSchema>;
export type Rev10Row=z.infer<typeof row>;
export function rev10Url(resource:string):string {return `${industryForecastBaseUrl()}/swl1-rev10/${resource}`;}
async function resource<T>(name:string,schema:z.ZodType<T>,signal:AbortSignal):Promise<T> {
  const response=await fetch(rev10Url(name),{signal});
  if(!response.ok)throw new Error(response.status===503?'REV10_INTEGRITY_BLOCKER':'REV10_API_UNAVAILABLE');
  return z.object({schemaVersion:z.literal('1.0.0'),data:schema,error:z.null()}).strict().parse(await response.json()).data;
}
export const fetchRev10Overview=(signal:AbortSignal)=>resource('overview',rev10OverviewSchema,signal);
export const fetchRev10Ranking=(signal:AbortSignal)=>resource('ranking',rev10RankingSchema,signal);

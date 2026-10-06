import { z } from 'zod';

const finite = z.number().finite();
const nullable = finite.nullable();
const component = z.object({ raw_prediction: finite, cross_section_zscore: finite, rank: z.number().int().positive() });
export const familySchema = z.object({
  family_id: z.enum(['swl2_ridge_v1', 'swl2_ridge_v2']), display_name: z.enum(['SWL2-Ridge-V1', 'SWL2-Ridge-V2']),
  legacy_identity: z.string(), generation: z.number().int(), industry_level: z.literal(2),
  current_role: z.literal('INDUSTRY_FORECAST_RESEARCH'), etf_productization_status: z.literal('RETIRED'),
  scientific_status: z.string(), historical_research: z.record(z.string(), z.string()),
});
export const rowSchema = z.object({industry_code: z.string(), industry_name: z.string(), fused_rank: z.number().int(), fused_score: finite,
  horizons: z.object({'10':component,'40':component,'120':component})});
const provenanceSchema = z.object({data_source:z.string(),source_commit:z.string(),snapshot_sha256:z.string(),data_cutoff:z.string(),available_at:z.string(),realized_series_type:z.literal('RECONSTRUCTED_SWL2_EQUAL_WEIGHT'),historical_membership:z.string()});
const forecastSchema = z.object({signal_date:z.string(),published_at:z.string(),data_cutoff:z.string(),source_commit:z.string(),model_contract_hash:z.string(),taxonomy_identity:z.string(),industry_count:z.number().int(),cross_section:z.array(rowSchema),provenance:provenanceSchema});
export const metricSchema = z.object({horizon:z.number(),matured_forecast_dates:z.number(),mean_rank_ic:nullable,median_rank_ic:nullable,positive_rank_ic_fraction:nullable,top5_mean_return:nullable,bottom5_mean_return:nullable,top5_bottom5_spread:nullable,universe_mean_return:nullable,confidence_status:z.string(),rolling:z.array(z.object({from:z.string(),through:z.string(),rank_ic:nullable,spread:finite})),worst_rolling_interval:z.object({from:z.string(),through:z.string(),rank_ic:nullable,spread:finite}).nullable()});
const evaluationSchema = z.object({signal_date:z.string(),horizon:z.number(),maturity_date:z.string(),realized_series_type:z.literal('RECONSTRUCTED_SWL2_EQUAL_WEIGHT'),provenance:provenanceSchema,
  metrics:z.object({rank_ic:nullable,predicted_top5:z.array(z.string()),actual_top5:z.array(z.string()),top5_overlap_count:z.number(),top5_overlap_rate:finite,mean_absolute_rank_error:finite,median_absolute_rank_error:finite,fused_top5_mean_return:finite,
    realized:z.array(z.object({industry_code:z.string(),predicted_rank:z.number(),realized_rank:z.number(),realized_return:finite,scientific_target:finite}))}),
  visual_trend_diagnostic:z.object({type:z.literal('NORMALIZED_RESEARCH_INDEX'),start:z.literal(1),label:z.literal('NON_TRADABLE_RESEARCH_DIAGNOSTIC'),points:z.array(z.object({date:z.string(),values:z.record(z.string(),finite),universe_equal_weight:finite}))})});
export const viewSchema=z.object({family:familySchema,status:z.string(),current:forecastSchema.nullable(),history:z.array(forecastSchema),evaluations:z.array(evaluationSchema),metrics:z.array(metricSchema)});
const comparisonValues=z.object({mean_rank_ic:nullable,median_rank_ic:nullable,positive_rank_ic_fraction:nullable,top5_bottom5_spread:nullable});
export const comparisonSchema=z.array(z.object({scope:z.literal('COMMON_FORWARD_WINDOW'),horizon:z.number(),matured_common_dates:z.array(z.string()),matured_common_date_count:z.number(),swl2_ridge_v1:comparisonValues,swl2_ridge_v2:comparisonValues,difference_v2_minus_v1:comparisonValues,confidence_status:z.string()}));
export type Family=z.infer<typeof familySchema>;
export type ForecastView=z.infer<typeof viewSchema>;
export type Comparison=z.infer<typeof comparisonSchema>;

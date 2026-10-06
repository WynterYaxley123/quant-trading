import { z } from 'zod';
import { industryForecastBaseUrl } from '@/lib/env';
import { familySchema, viewSchema, comparisonSchema } from './contracts';

async function get<T>(resource:string,schema:z.ZodType<T>,signal:AbortSignal):Promise<T> {
  const response=await fetch(`${industryForecastBaseUrl()}/${resource}`,{signal});
  if(!response.ok)throw new Error('Industry Forecast API unavailable or integrity blocked');
  const envelope=z.object({schemaVersion:z.literal('1.0.0'),data:schema,error:z.null()}).parse(await response.json());
  return envelope.data;
}
export const fetchFamilies=(signal:AbortSignal)=>get('families',z.array(familySchema),signal);
export const fetchForecast=(family:string,signal:AbortSignal)=>get(`${family.replaceAll('_','-')}/current`,viewSchema,signal);
export const fetchComparison=(signal:AbortSignal)=>get('swl2-ridge/compare',comparisonSchema,signal);

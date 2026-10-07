import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import { createAppRouter } from '@/app/router';
import { IndustryForecastPage } from '@/industry-forecast/Page';
import { fetchFamilies, fetchForecast, fetchComparison } from '@/industry-forecast/client';
import { comparisonSchema, familySchema, viewSchema } from '@/industry-forecast/contracts';
import { setEtfQuantPortForTesting } from '@/etf-quant/data-port';

vi.mock('@/industry-forecast/client',()=>({fetchFamilies:vi.fn(),fetchForecast:vi.fn(),fetchComparison:vi.fn()}));
const family=familySchema.parse({family_id:'swl2_ridge_v1',display_name:'SWL2-Ridge-V1',legacy_identity:'ETF_QUANT_V1',generation:1,industry_level:2,current_role:'INDUSTRY_FORECAST_RESEARCH',etf_productization_status:'RETIRED',taxonomy_scope:'SWCLASS2021',taxonomy_universe_size:134,model_universe_size:107,model_universe_hash:'b'.repeat(64),taxonomy_only_industries:Array.from({length:27},(_,i)=>`T${i}`),taxonomy_only_status:'NOT_IN_FROZEN_MODEL_UNIVERSE',scientific_status:'FROZEN_BASELINE',historical_research:{validation:'SEALED',final_oos:'SEALED'}});
const second=familySchema.parse({...family,family_id:'swl2_ridge_v2',display_name:'SWL2-Ridge-V2',legacy_identity:'ETF_QUANT_V2',generation:2,model_universe_size:124,taxonomy_only_industries:Array.from({length:10},(_,i)=>`T${i}`),scientific_status:'PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE'});
const metrics=[10,40,120].map(horizon=>({horizon,matured_forecast_dates:0,mean_rank_ic:null,median_rank_ic:null,positive_rank_ic_fraction:null,top5_mean_return:null,bottom5_mean_return:null,top5_bottom5_spread:null,universe_mean_return:null,confidence_status:'INSUFFICIENT_FORWARD_EVIDENCE',rolling:[],worst_rolling_interval:null}));
const provenance={data_source:'SYNTHETIC_SOURCE_C',source_commit:'a'.repeat(40),snapshot_sha256:'b'.repeat(64),data_cutoff:'2028-01-04',available_at:'2028-01-04T16:00:00+08:00',realized_series_type:'RECONSTRUCTED_SWL2_EQUAL_WEIGHT',historical_membership:'RECONSTRUCTED'} as const;
function empty() {return viewSchema.parse({family,status:'NO_FORWARD_FORECASTS',current:null,history:[],evaluations:[],metrics});}
function published() {
  const forecast={event_hash:'c'.repeat(64),event_type:'FORECAST',signal_date:'2028-01-04',published_at:'2028-01-04T16:00:00+08:00',data_cutoff:'2028-01-04',source_commit:'a'.repeat(40),model_contract_hash:'b'.repeat(64),taxonomy_identity:'SYNTHETIC_SWL2',industry_count:107,forecast_row_count:107,taxonomy_universe_size:family.taxonomy_universe_size,model_universe_size:family.model_universe_size,model_universe_hash:family.model_universe_hash,provenance,
    cross_section:Array.from({length:107},(_,i)=>({industry_code:`S${i}`,industry_name:`合成行业 ${i}`,fused_rank:i+1,fused_score:-i,horizons:Object.fromEntries([10,40,120].map(h=>[h,{raw_prediction:-i,cross_section_zscore:-i,rank:i+1}]))}))};
  return viewSchema.parse({...empty(),status:'FORWARD_FORECAST',current:forecast,history:[forecast]});
}
beforeEach(()=>{
  vi.mocked(fetchFamilies).mockResolvedValue([family,second]);vi.mocked(fetchForecast).mockResolvedValue(empty());
  vi.mocked(fetchComparison).mockResolvedValue(comparisonSchema.parse([10,40,120].map(horizon=>({scope:'COMMON_FORWARD_WINDOW',metric_scope:'COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC',common_industry_counts:{},raw_return_compatibility:'NO_COMMON_MATURED_OBSERVATIONS',centered_target_equality_required:false,horizon,matured_common_dates:[],matured_common_date_count:0,swl2_ridge_v1:{mean_rank_ic:null,median_rank_ic:null,positive_rank_ic_fraction:null,top5_bottom5_spread:null,mean_absolute_rank_error:null,median_absolute_rank_error:null,top5_overlap_count:null,top5_overlap_rate:null},swl2_ridge_v2:{mean_rank_ic:null,median_rank_ic:null,positive_rank_ic_fraction:null,top5_bottom5_spread:null,mean_absolute_rank_error:null,median_absolute_rank_error:null,top5_overlap_count:null,top5_overlap_rate:null},difference_v2_minus_v1:{mean_rank_ic:null,median_rank_ic:null,positive_rank_ic_fraction:null,top5_bottom5_spread:null,mean_absolute_rank_error:null,median_absolute_rank_error:null,top5_overlap_count:null,top5_overlap_rate:null},confidence_status:'INSUFFICIENT_FORWARD_EVIDENCE'}))));
});
afterEach(()=>{cleanup();vi.clearAllMocks();setEtfQuantPortForTesting(null);});
describe('canonical industry forecast',()=>{
  it('uses full family names, honest empty states and null metrics',async()=>{
    render(<IndustryForecastPage/>);
    expect(await screen.findByText('No forward forecasts yet. 不回填历史研究结果。')).toBeInTheDocument();
    expect(screen.getByText('No matured forward observations yet.')).toBeInTheDocument();
    expect(screen.getByRole('option',{name:'SWL2-Ridge-V1'})).toBeInTheDocument();
    expect(screen.getByRole('option',{name:'SWL2-Ridge-V2'})).toBeInTheDocument();
    expect(screen.queryByText('V1')).toBeNull();expect(screen.queryByText('V2')).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText('策略家族'),'swl2_ridge_v2');
    expect(fetchForecast).toHaveBeenLastCalledWith('swl2_ridge_v2',expect.any(AbortSignal));
  });
  it('shows the complete actual universe and PENDING without future values',async()=>{
    vi.mocked(fetchForecast).mockResolvedValue(published());render(<IndustryForecastPage/>);
    expect(await screen.findByRole('heading',{name:'Full Ranking · 107 industries'})).toBeInTheDocument();
    const table=screen.getAllByRole('table')[0]!;expect(within(table).getAllByRole('row')).toHaveLength(108);
    expect(screen.getByText('H10: PENDING · H40: PENDING · H120: PENDING')).toBeInTheDocument();
    expect(screen.getAllByText(/RECONSTRUCTED_SWL2_EQUAL_WEIGHT/).length).toBeGreaterThan(0);
    expect(screen.queryByText('OFFICIAL_SWL2_INDEX')).toBeNull();
    for(const text of [/initial capital/i,/position value/i,/commission/i,/slippage/i,/account value/i])expect(screen.queryByText(text)).toBeNull();
  });
  it('renders only matured H10 outcomes and preserves pending longer horizons',async()=>{
    const value=published();value.metrics[0]={...value.metrics[0]!,matured_forecast_dates:1,mean_rank_ic:1,median_rank_ic:1,positive_rank_ic_fraction:1,top5_mean_return:.03,bottom5_mean_return:-.01,top5_bottom5_spread:.04,universe_mean_return:.01};
    value.evaluations=[{signal_date:'2028-01-04',horizon:10,maturity_date:'2028-01-18',realized_series_type:'RECONSTRUCTED_SWL2_EQUAL_WEIGHT',provenance,metrics:{rank_ic:1,predicted_top5:['S0','S1','S2','S3','S4'],actual_top5:['S0','S1','S2','S3','S4'],top5_overlap_count:5,top5_overlap_rate:1,mean_absolute_rank_error:0,median_absolute_rank_error:0,fused_top5_mean_return:.03,realized:value.current!.cross_section.map(r=>({industry_code:r.industry_code,predicted_rank:r.fused_rank,realized_rank:r.fused_rank,realized_return:.03,scientific_target:.02}))},visual_trend_diagnostic:{type:'NORMALIZED_RESEARCH_INDEX',start:1,label:'NON_TRADABLE_RESEARCH_DIAGNOSTIC',points:[]}}];
    vi.mocked(fetchForecast).mockResolvedValue(value);render(<IndustryForecastPage/>);
    expect(await screen.findByText('H10: MATURED · H40: PENDING · H120: PENDING')).toBeInTheDocument();
    expect(screen.getByText(/Overlap 5\/5/)).toBeInTheDocument();
    expect(screen.getByRole('heading',{name:'Trend View · normalized start 1.0'})).toBeInTheDocument();
    expect(screen.getByText(/Actual future Top5/)).toBeInTheDocument();
  });
  it('fails visibly when provenance or service schema is unavailable',async()=>{
    vi.mocked(fetchForecast).mockRejectedValue(new Error('blocked'));render(<IndustryForecastPage/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('integrity blocked');
    expect(screen.queryByText('No forward forecasts yet. 不回填历史研究结果。')).toBeNull();
  });
  it('default route does not invoke the legacy ETF capability or account API',async()=>{
    const legacy=vi.fn(async()=>{throw new Error('unexpected ETF access');});
    setEtfQuantPortForTesting({getStatus:legacy,getSnapshot:legacy,getReadiness:legacy});
    const router=createAppRouter(createMemoryHistory({initialEntries:['/']}));
    await act(async()=>{render(<RouterProvider router={router}/>);await router.load();});
    expect((await screen.findAllByRole('heading',{name:'Industry Forecast'})).length).toBeGreaterThan(0);
    expect(legacy).not.toHaveBeenCalled();
    expect(screen.queryByRole('link',{name:'模拟持仓'})).toBeNull();
    expect(screen.getByRole('heading',{name:/COMMON_FORWARD_WINDOW/})).toBeInTheDocument();
  });
});

it('renders V2 full frozen rows and dynamic inventory metadata',async()=>{
  const value=published();value.family=second;
  value.current={...value.current!,industry_count:second.model_universe_size,forecast_row_count:second.model_universe_size,model_universe_size:second.model_universe_size,cross_section:Array.from({length:second.model_universe_size},(_,i)=>({industry_code:`S${i}`,industry_name:`合成行业 ${i}`,fused_rank:i+1,fused_score:-i,horizons:{'10':{raw_prediction:-i,cross_section_zscore:-i,rank:i+1},'40':{raw_prediction:-i,cross_section_zscore:-i,rank:i+1},'120':{raw_prediction:-i,cross_section_zscore:-i,rank:i+1}}}))};
  value.history=[value.current];vi.mocked(fetchForecast).mockResolvedValue(value);render(<IndustryForecastPage/>);
  expect(await screen.findByRole('heading',{name:'Full Ranking · 124 industries'})).toBeInTheDocument();
  expect(within(screen.getAllByRole('table')[0]!).getAllByRole('row')).toHaveLength(125);
  expect(screen.getByText(/Taxonomy \(SWCLASS2021\): 134 · Frozen model universe: 124/)).toBeInTheDocument();
  expect(screen.getByText(/Centered target 不要求跨家族相等/)).toBeInTheDocument();
});

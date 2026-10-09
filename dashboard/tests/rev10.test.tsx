import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Rev10Page } from '@/industry-forecast/Rev10Page';
import { rev10OverviewSchema, rev10RankingSchema } from '@/industry-forecast/rev10-client';
const read=(name:string)=>readFileSync(resolve(process.cwd(),'..',name),'utf8');
const sha=(raw:string)=>createHash('sha256').update(raw).digest('hex');
function fixtures() {
  const raw=read('reports/research/swl1_short_horizon_exploration/research-summary.json'),summary=JSON.parse(raw);
  const model=JSON.parse(read('config/research/swl1-rev10-short-v1.json'));
  const models=Object.fromEntries(['S0','S1','S2','S3','S4'].map(id=>[id,Object.fromEntries(['5','10'].map(h=>{const m=summary.models[id][h];return [h,{rank_ic:m.rank_ic,signal_count:m.signal_count,calendar_blocks:m.calendar_blocks,raw_spread:m.raw_top5_minus_bottom5_spread}];}))]));
  const overview=rev10OverviewSchema.parse({model,model_hash:sha(read('config/research/swl1-rev10-short-v1.json')),classification:'EXPLORATORY_POST_HOC',historical_cutoff:'2026-09-29',models,decision:'A',limitations:[],readiness:{model_implemented:true,historical_exploration_available:true,preregistration_draft_ready:true,formal_preregistration_active:false,production_source_admitted:false,production_signature_authority:'SIGNATURE_AUTHORITY_NOT_ESTABLISHED',statistical_design:'STATISTICAL_DESIGN_PENDING',prospective_observations_collected:0,independent_validation_complete:false,data_status:'DATA_SOURCE_NOT_READY',real_sources_admitted:0,historical_access_isolation:'NOT_CERTIFIED',certified_historically_unseen_sessions:0,swl1_v1:'FAILED_VALIDATION',swl1_v2:'FAILED_VALIDATION',final_oos_opened:false},charts:[['signal-rankic','信号'],['temporal-blocks','四个固定时间块'],['ridge-comparison','Ridge'],['factor-target-correlations','相关性'],['industry-sensitivity','敏感性'],['concentration-turnover','换手']].map(([id,title])=>({id,title})),evidence:['design','chinese-report','acceptance','data-boundary','research-decision','source-qualification','preregistration-draft'].map(id=>({id,reference:id})),research_pr:'https://github.com/WynterYaxley123/quant-trading/pull/36',source_hashes:{summary:sha(raw),boundary:sha(read('reports/research/swl1_short_horizon_exploration/data-boundary.json'))}});
  const universe=JSON.parse(read('config/research/swl1-ridge-v1-universe.json'));
  const asof='2023-02-01';
  const rows=universe.industries.map((code:string,i:number)=>({rank:i+1,industry_code:code,industry_name:`合成测试行业 ${i}`,name_verified:false,rev10_score:(30-i)/10000,relative_score:(14.5-i)/10000,trailing_mean_return:-(30-i)/10000,data_asof:asof,data_completeness:'10_OF_10_FINITE_SESSIONS',source_generation:'SYNTHETIC_ONLY_TEST_FIXTURE'}));
  const ranking=rev10RankingSchema.parse({status:'HISTORICAL_REPLAY',namespace:'RESEARCH_REPLAY_ONLY',asof,count:30,complete_universe:true,ranking_basis:'REV10_DESCENDING_CODE_ASCENDING_TIES',rows,top5:rows.slice(0,5),bottom5:[...rows].reverse().slice(0,5),manifest_sha256:'a'.repeat(64),source_commit:model.source_commit,source_generation:'SYNTHETIC_ONLY_TEST_FIXTURE',window_sessions:['2023-01-18','2023-01-19','2023-01-20','2023-01-23','2023-01-24','2023-01-25','2023-01-26','2023-01-27','2023-01-30',asof]});
  return {overview,ranking};
}
function mock(overview:unknown,ranking:unknown,failOverview=false,failRanking=false) {
  vi.stubGlobal('fetch',vi.fn((url:string)=>Promise.resolve(new Response(JSON.stringify({schemaVersion:'1.0.0',data:url.includes('/overview')?overview:ranking,error:null}),{status:url.includes('/overview')&&failOverview||url.includes('/ranking')&&failRanking?503:200}))));
}
afterEach(()=>vi.unstubAllGlobals());
describe('REV10 research console',()=>{
  it('displays source-bound metrics and distinct blocked future states',async()=>{
    const f=fixtures();mock(f.overview,f.ranking);render(<Rev10Page/>);
    const mean=f.overview.models.S2['10'].rank_ic.mean;
    expect(mean).not.toBeNull();
    expect((await screen.findAllByText(`${Number(mean)>0?'+':''}${Number(mean).toFixed(6)}`))[0]).toBeVisible();
    expect(screen.getByText('EXPLORATORY_POST_HOC · 后验探索')).toBeVisible();
    expect(screen.getByText('未激活')).toBeVisible();expect(screen.getByText('0 · 未就绪')).toBeVisible();
    expect(screen.queryByText('VALIDATION_PASS')).not.toBeInTheDocument();
  });
  it('switches verified extremes and all 30 synthetic rows',async()=>{
    const f=fixtures();mock(f.overview,f.ranking);render(<Rev10Page/>);
    const table=await screen.findByRole('table',{name:'REV10 历史行业排名'});
    expect(within(table).getAllByRole('row')).toHaveLength(6);
    await userEvent.click(screen.getByRole('button',{name:'Bottom5'}));expect(within(table).getByText('合成测试行业 29')).toBeVisible();
    await userEvent.click(screen.getByRole('button',{name:'全部 30 行业'}));expect(within(table).getAllByRole('row')).toHaveLength(31);
    expect(screen.getByText(/不代表今日行情/)).toBeVisible();
  });
  it('keeps historical aggregates when private preview is absent',async()=>{
    const f=fixtures();mock(f.overview,{status:'UNAVAILABLE',reason:'LOCAL_PRIVATE_REPLAY_NOT_CONFIGURED',asof:null,count:0,rows:[],top5:[],bottom5:[]});render(<Rev10Page/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('排名不可用');expect(screen.queryByRole('table',{name:'REV10 历史行业排名'})).not.toBeInTheDocument();
    expect(screen.getByRole('table',{name:'四个时间块'})).toBeVisible();
  });
  it('corrupted ranking fails closed while source-bound metrics remain',async()=>{
    const f=fixtures();mock(f.overview,{...f.ranking,count:29});render(<Rev10Page/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('完整性校验失败');expect(screen.queryByRole('table',{name:'REV10 历史行业排名'})).not.toBeInTheDocument();
    expect(screen.getByRole('table',{name:'历史基线比较'})).toBeVisible();
  });
  it('API disconnect shows explicit error and offline entry, without fake data',async()=>{
    const f=fixtures();mock(f.overview,f.ranking,true,true);render(<Rev10Page/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('暂不可用');expect(screen.getByRole('link',{name:'打开本地离线成果包'})).toHaveAttribute('href','/offline-review/index.html');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
  it('changes among original charts and shows four blocks',async()=>{
    const f=fixtures();mock(f.overview,f.ranking);render(<Rev10Page/>);
    await screen.findByRole('table',{name:'四个时间块'});await userEvent.click(screen.getByRole('button',{name:'Ridge'}));
    await waitFor(()=>expect(screen.getByRole('img',{name:'Ridge'})).toHaveAttribute('src',expect.stringContaining('/chart/ridge-comparison')));
  });
});

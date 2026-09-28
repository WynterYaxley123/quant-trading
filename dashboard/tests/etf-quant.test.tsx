import { afterEach,beforeEach,describe,expect,it } from 'vitest';
import { screen,within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMockApiAdapter } from '@/api/adapters/mock-api';
import { createEtfQuantApi,setEtfQuantPortForTesting } from '@/etf-quant/data-port';
import { snapshotSchema } from '@/etf-quant/contracts';
import { ResearchApiError } from '@/api/errors';
import { renderApp } from './test-utils';
import { etfFixture,notReachedReadiness,runningFixture,trainedFixture } from './etf-quant-fixtures';

beforeEach(()=>{const data=etfFixture();const readiness=notReachedReadiness();setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});});
afterEach(()=>setEtfQuantPortForTesting(null));

describe('ETF Quant independent product',()=>{
  for (const [path,title] of [['overview','ETF Quant 总览'],['portfolio','模拟持仓组合'],['rankings','行业融合排名'],
    ['factors','因子与模型系数'],['mappings','ETF 映射准入'],['trades','模拟成交流水'],
    ['benchmarks','基准 · CSI 300'],['health','ETF Quant 数据健康']]) {
    it(`renders ${path} independently`,async()=>{
      await renderApp(`/etf-quant/${path}`);
      expect(await screen.findByRole('heading',{name:title})).toBeInTheDocument();
      expect(screen.getAllByText(/SIMULATION_ONLY/).length).toBeGreaterThan(0);
      expect(await screen.findByText(/NOT OFFICIAL SHENWAN INDEX/)).toBeInTheDocument();
    });
  }
  it('shows ETF capability after Research, not from a Research flag',async()=>{
    await renderApp('/etf-quant/overview');
    const nav=screen.getByRole('navigation',{name:'研究页面导航'});
    expect(within(nav).getByRole('link',{name:'总览'})).toBeInTheDocument();
    expect(within(nav).getByRole('link',{name:'Shadow 准备'})).toBeInTheDocument();
    const groups=within(nav).getAllByText(/^(研究|ETF Quant|诊断)$/).filter(g=>g.tagName==='P');
    expect(groups.map(g=>g.textContent)).toEqual(['研究','ETF Quant','诊断']);
  });
  it('Research API disconnected does not block ETF route',async()=>{
    const port=createMockApiAdapter();
    const fail=async()=>{throw new ResearchApiError('NETWORK_UNREACHABLE');};
    await renderApp('/etf-quant/portfolio',{...port,getHealth:fail,getCapabilities:fail,getResearchStatus:fail,getRuns:fail});
    expect(await screen.findByRole('heading',{name:'模拟持仓组合'})).toBeInTheDocument();
    expect(await screen.findByText('Shadow 尚未启动')).toBeInTheDocument();
  });
  it('blocked account has no fake equity, NAV chart or initial holdings',async()=>{
    await renderApp('/etf-quant/portfolio');
    expect(await screen.findByText('Shadow 尚未启动')).toBeInTheDocument();
    expect(screen.queryByRole('img',{name:/forward epoch NAV/})).not.toBeInTheDocument();
    expect(screen.queryByText('¥10,000.00')).not.toBeInTheDocument();
    expect(screen.getByText(/没有 epoch，因此没有持仓/)).toBeInTheDocument();
  });
  it('rankings default Top20, show all and switch all four horizons',async()=>{
    await renderApp('/etf-quant/rankings');
    expect(await screen.findByText('20 / 25 个行业')).toBeInTheDocument();
    expect(screen.queryByText('801024')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button',{name:'显示全部行业'}));
    expect(screen.getByText('801024')).toBeInTheDocument();
    for(const h of ['10d','40d','120d','fusion']) {
      await userEvent.click(screen.getByRole('tab',{name:h}));
      expect(screen.getByRole('tab',{name:h})).toHaveAttribute('aria-selected','true');
    }
  });
  it('factors use frozen 5/19/19 names and signed coefficients',async()=>{
    const data=trainedFixture();const readiness=notReachedReadiness();setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/factors');
    expect(await screen.findByRole('table',{name:'10d 因子和系数'})).toBeInTheDocument();
    expect(screen.getByText('-0.01')).toBeInTheDocument();
    expect(screen.getByText(/label cutoff：2026-03-01/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab',{name:'40d'}));
    expect(screen.getByRole('table',{name:'40d 因子和系数'})).toBeInTheDocument();
    expect(screen.getByText('rsi')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab',{name:'120d'}));
    expect(screen.getByRole('table',{name:'120d 因子和系数'})).toBeInTheDocument();
  });
  it('mapping blocked is explicit and benchmarks are deferred',async()=>{
    await renderApp('/etf-quant/mappings');
    expect(await screen.findByRole('heading',{name:'MAPPING_ADMISSION_BLOCKED'})).toBeInTheDocument();
    expect(screen.getByText('NO_VERIFIED_EVIDENCE')).toBeInTheDocument();
  });
  it('missing mapping explanation never becomes a false admission claim',async()=>{
    const data=etfFixture();data.mappings.reason=null;
    const readiness=notReachedReadiness();
    setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/mappings');
    expect(await screen.findByText(/不可据此推断已有五个独立、已验证 ETF/)).toBeInTheDocument();
    expect(screen.queryByText('五个独立、已验证 ETF 已通过准入。')).not.toBeInTheDocument();
  });
  it('unreachable API never falls back to synthetic holdings',async()=>{
    setEtfQuantPortForTesting(createEtfQuantApi('http://127.0.0.1:3312',async()=>{throw new TypeError('SYNTHETIC transport failure');}));
    await renderApp('/etf-quant/portfolio');
    expect(await screen.findByText(/没有自动 mock fallback/)).toBeInTheDocument();
    expect(screen.queryByText('Shadow 尚未启动')).not.toBeInTheDocument();
  });
  it('DTO rejects fake pre-epoch NAV and broker activation',()=>{
    const data=etfFixture();
    expect(snapshotSchema.safeParse({...data,status:{...data.status,broker_enabled:true}}).success).toBe(false);
    expect(snapshotSchema.safeParse({...data,portfolio_summary:{...data.portfolio_summary,total_equity:'10000'}}).success).toBe(false);
  });
  it('independent API envelope and malformed DTO guards',async()=>{
    const bad=createEtfQuantApi('http://localhost:3312',async()=>new Response(JSON.stringify({schemaVersion:'1.0.0',data:{},error:null,
      meta:{runId:null,manifestSha256:null,etfQuant:true}}),{status:200}));
    await expect(bad.getStatus()).rejects.toThrow('ETF Quant 数据完整性');
    expect(()=>createEtfQuantApi('https://example.invalid')).toThrow();
  });
  it('synthetic forward holdings and CSI300 chart render only after an epoch',async()=>{
    const data=runningFixture();const readiness=notReachedReadiness();setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/portfolio');
    expect(await screen.findByText('SYNTHETIC ETF TEST ONLY')).toBeInTheDocument();
    expect(screen.getByText('SYNTHETIC INDUSTRY')).toBeInTheDocument();
    expect(screen.getByRole('heading',{name:'Forward NAV · CSI 300'})).toBeInTheDocument();
    expect(screen.getByText(/1 个 forward epoch NAV 点/)).toBeInTheDocument();
  });
  it('rejects mixed immutable generations across independent endpoint reads',async()=>{
    const api=createEtfQuantApi('http://localhost:3312',async url=>{
      const endpoint=String(url).split('/v1/')[1];const data=etfFixture();
      const values:Record<string,unknown>={status:data.status,strategy:data.strategy,models:data.models,
        'rankings/10d':data.rankings['10d'],'rankings/40d':data.rankings['40d'],'rankings/120d':data.rankings['120d'],'rankings/fusion':data.rankings.fusion,
        'portfolio/summary':data.portfolio_summary,'portfolio/holdings':data.holdings,'portfolio/nav':data.nav,trades:data.trades,
        mappings:data.mappings,'benchmark/csi300':data.benchmark,health:data.health};
      return new Response(JSON.stringify({schemaVersion:'1.0.0',data:values[endpoint!],error:null,
        meta:{runId:endpoint==='status'?'SYNTHETIC_A':'SYNTHETIC_B',manifestSha256:'a'.repeat(64),etfQuant:true}}),{status:200});
    });
    await expect(api.getSnapshot()).rejects.toThrow('快照已更新');
  });
});

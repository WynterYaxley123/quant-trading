import { afterEach,beforeEach,describe,expect,it } from 'vitest';
import { screen,within } from '@testing-library/react';
import { setEtfQuantPortForTesting } from '@/etf-quant/data-port';
import { EtfQuantDataError } from '@/etf-quant/data-port';
import { renderApp } from './test-utils';
import { etfFixture,gatesReadinessFixture,notReachedReadiness } from './etf-quant-fixtures';

beforeEach(()=>{const data=etfFixture();const readiness=notReachedReadiness();
  setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});});
afterEach(()=>setEtfQuantPortForTesting(null));

describe('ETF Quant Readiness view',()=>{
  it('renders the gate list with honest per-gate statuses',async()=>{
    const data=etfFixture();const readiness=gatesReadinessFixture();
    setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/readiness');
    expect(await screen.findByRole('heading',{name:'Shadow 启动准备状态'})).toBeInTheDocument();
    expect(screen.getAllByText(/SIMULATION_ONLY/).length).toBeGreaterThan(0);
    for(const name of ['DATA_FRESHNESS','MAPPING_ADMISSION','OVERSEAS_BENCHMARK','MODEL_WARMUP']) {
      expect(await screen.findByText(name)).toBeInTheDocument();
    }
    const list=screen.getAllByRole('list')[0]!;
    expect(within(list).getByText('通过')).toBeInTheDocument();
    expect(within(list).getByText('阻断')).toBeInTheDocument();
    expect(within(list).getByText('暂缓')).toBeInTheDocument();
    expect(within(list).getByText('未达成')).toBeInTheDocument();
    expect(screen.getByText('证据：NO_VERIFIED_EVIDENCE')).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC TEST ONLY/)).toBeInTheDocument();
  });
  it('BLOCKED overall renders a blocking banner, never a success',async()=>{
    const data=etfFixture();const readiness=gatesReadinessFixture();
    setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/readiness');
    expect(await screen.findByText('存在阻断门控，Shadow 尚不可启动')).toBeInTheDocument();
    expect(screen.getByText(/shadow_epoch_created = false/)).toBeInTheDocument();
    expect(screen.getByText(/shadow_started = false/)).toBeInTheDocument();
    expect(screen.queryByText('全部启动门控已通过')).not.toBeInTheDocument();
  });
  it('NOT_REACHED without an artifact is an explicit honest empty state',async()=>{
    await renderApp('/etf-quant/readiness');
    expect(await screen.findByText('准备状态评估尚未完成')).toBeInTheDocument();
    expect(screen.getByText('准备状态报告尚未发布')).toBeInTheDocument();
    expect(screen.getByText(/不会以历史数据代替评估结果/)).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });
  it('readiness view stays available when the snapshot endpoint is unreachable',async()=>{
    const data=etfFixture();const readiness=gatesReadinessFixture();
    setEtfQuantPortForTesting({async getStatus(){return data.status;},
      async getSnapshot(){throw new EtfQuantDataError('UNREACHABLE');},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/readiness');
    expect(await screen.findByRole('heading',{name:'Shadow 启动准备状态'})).toBeInTheDocument();
    expect(await screen.findByText('MAPPING_ADMISSION')).toBeInTheDocument();
  });
  it('readiness failure shows the no-fallback error card',async()=>{
    const data=etfFixture();
    setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},
      async getReadiness(){throw new EtfQuantDataError('UNREACHABLE');}});
    await renderApp('/etf-quant/readiness');
    expect(await screen.findByText(/没有自动 mock fallback/)).toBeInTheDocument();
  });
  it('overview surfaces readiness overall as a status, not as fabricated progress',async()=>{
    const data=etfFixture();const readiness=gatesReadinessFixture();
    setEtfQuantPortForTesting({async getStatus(){return data.status;},async getSnapshot(){return data;},async getReadiness(){return readiness;}});
    await renderApp('/etf-quant/overview');
    expect(await screen.findByRole('heading',{name:'ETF Quant 总览'})).toBeInTheDocument();
    expect((await screen.findAllByText('存在阻断门控，Shadow 尚不可启动')).length).toBeGreaterThan(0);
    expect(screen.getByText(/门控 4 项：通过 1 · 阻断 1 · 暂缓 1 · 未达成 1/)).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'查看完整启动门控清单 →'})).toBeInTheDocument();
  });
});

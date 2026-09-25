import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from './test-utils';

describe('Overview page', () => {
  it('shows research state first: development, sealed validation and OOS, non-executable, not tradable', async () => {
    await renderApp('/');

    // Global banner is persistently visible
    expect((await screen.findAllByText('Development（开发集）')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('不可执行')).toBeInTheDocument();
    expect(screen.getByText('Validation（验证集）：已封存')).toBeInTheDocument();
    expect(screen.getByText('Final OOS（最终样本外）：已封存')).toBeInTheDocument();

    // Status cards
    expect((await screen.findAllByText('研究阶段')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('已封存').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('可执行')).toBeInTheDocument();
    expect(screen.getByText('可交易')).toBeInTheDocument();
    expect(screen.getByText('严格 PIT')).toBeInTheDocument();
    expect(screen.getAllByText('否').length).toBeGreaterThanOrEqual(3);
  });

  it('renders D0-D3 candidate cards with unit hints and promotion status', async () => {
    await renderApp('/');
    for (const candidateId of ['D0', 'D1', 'D2', 'D3']) {
      expect(await screen.findByText(candidateId)).toBeInTheDocument();
    }
    expect(screen.getAllByText('加权 RankIC（无量纲）').length).toBe(4);
    expect(screen.getAllByText('加权超额收益差').length).toBe(4);
    expect((await screen.findAllByText('进入进一步研究')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('未晋级')).toBeInTheDocument();
  });

  it('shows run context with abbreviated hashes', async () => {
    await renderApp('/');
    expect(await screen.findByText('当前研究运行')).toBeInTheDocument();
    expect(screen.getByText('Git Commit')).toBeInTheDocument();
    expect(screen.getByText('研究协议 Hash')).toBeInTheDocument();
    expect(screen.getByText('行业数据快照 ID')).toBeInTheDocument();
  });

  it('never shows fake backtest metrics', async () => {
    await renderApp('/');
    await screen.findAllByText('Development（开发集）');
    for (const banned of [/sharpe/i, /sortino/i, /drawdown/i, /equity curve/i, /win rate/i, /profit/i, /pnl/i]) {
      expect(screen.queryByText(banned)).toBeNull();
    }
  });

  it('sealed phases expose no unlock or override controls', async () => {
    await renderApp('/');
    await screen.findAllByText('Development（开发集）');
    expect(
      screen.queryByRole('button', { name: /unlock|view anyway|override|reveal sealed/i }),
    ).toBeNull();
    expect(screen.queryByRole('link', { name: /validation detail|oos detail/i })).toBeNull();
  });
});

describe('Mock data banner', () => {
  it('is shown only when VITE_DATA_MODE=mock', async () => {
    vi.stubEnv('VITE_DATA_MODE', 'mock');
    await renderApp('/');
    // Banner badge + header chip both mark mock mode.
    expect((await screen.findAllByText('模拟数据')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/MOCK DATA/)).toBeInTheDocument();
    vi.unstubAllEnvs();
  });

  it('is not shown in api mode (the default)', async () => {
    await renderApp('/');
    await screen.findAllByText('Development（开发集）');
    expect(screen.queryByText('模拟数据')).toBeNull();
    expect(screen.getByText('正式数据接口')).toBeInTheDocument();
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMockApiAdapter } from '@/api/adapters/mock-api';
import { ResearchApiError } from '@/api/errors';
import { EtfQuantDataError, setEtfQuantPortForTesting } from '@/etf-quant/data-port';
import { renderApp } from './test-utils';
import { etfFixture, notReachedReadiness } from './etf-quant-fixtures';

beforeEach(() => {
  const data = etfFixture();
  setEtfQuantPortForTesting({
    async getStatus() { return data.status; },
    async getSnapshot() { return data; },
    async getReadiness() { return notReachedReadiness(); },
  });
});
afterEach(() => { setEtfQuantPortForTesting(null); vi.restoreAllMocks(); });

function emptyResearch() {
  const port = createMockApiAdapter();
  return {
    ...port,
    async getResearchStatus() { return { ...await port.getResearchStatus(), phase: 'NOT_CONFIGURED' }; },
    getRuns: vi.fn(async () => []),
    getCandidates: vi.fn(port.getCandidates),
    getIntegrity: vi.fn(port.getIntegrity),
    getMetrics: vi.fn(port.getMetrics),
    getPredictions: vi.fn(port.getPredictions),
    getDailyMetrics: vi.fn(port.getDailyMetrics),
    getDiagnostics: vi.fn(port.getDiagnostics),
  };
}

describe('unified console observation', () => {
  for (const path of ['/', '/candidates', '/development', '/sectors', '/diagnostics', '/integrity']) {
    it(`renders a connected empty state at ${path} without requesting run results`, async () => {
      const port = emptyResearch();
      await renderApp(path, port);
      expect(await screen.findByText('Research API 已连接')).toBeInTheDocument();
      expect(screen.getByText('未配置获准的 Development 研究产物。')).toBeInTheDocument();
      expect(screen.queryByText('API DISCONNECTED')).not.toBeInTheDocument();
      const services = screen.getByRole('region', { name: '控制台服务' });
      expect(within(services).getAllByText('READY')).toHaveLength(3);
      for (const request of [port.getCandidates, port.getIntegrity, port.getMetrics,
        port.getPredictions, port.getDailyMetrics, port.getDiagnostics]) expect(request).not.toHaveBeenCalled();
    });
  }

  it('keeps a real disconnected service visible and gives the unified startup command', async () => {
    const port = emptyResearch();
    port.getHealth = async () => { throw new ResearchApiError('NETWORK_UNREACHABLE'); };
    await renderApp('/', port);
    expect(await screen.findByText('API DISCONNECTED')).toBeInTheDocument();
    expect(screen.getByText(/运行 scripts\/Start-EtfQuantConsole.ps1/)).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: '控制台服务' })).getByText('DISCONNECTED')).toBeInTheDocument();
    expect(screen.queryByText('Research API 已连接')).not.toBeInTheDocument();
  });

  it('keeps unknown routes visible when no approved Research artifacts exist', async () => {
    await renderApp('/unknown-console-page', emptyResearch());
    expect(await screen.findByText('页面不存在')).toBeInTheDocument();
    expect(screen.queryByText('Research API 已连接')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '返回概览' })).toBeInTheDocument();
  });

  it('does not convert an artifact integrity failure into an empty dataset', async () => {
    const port = emptyResearch();
    port.getRuns = vi.fn(async () => { throw new ResearchApiError('ARTIFACT_SCHEMA_ERROR'); });
    await renderApp('/', port);
    expect(await screen.findByText('错误代码：ARTIFACT_SCHEMA_ERROR')).toBeInTheDocument();
    expect(screen.queryByText('Research API 已连接')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: '控制台服务' })).getByText('DEGRADED')).toBeInTheDocument();
  });

  it('rechecks after empty-state retry', async () => {
    const port = emptyResearch();
    await renderApp('/', port);
    await screen.findByText('Research API 已连接');
    const before = port.getRuns.mock.calls.length;
    expect(screen.getAllByText('未配置 Development 产物').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: '重新检查产物' }));
    await screen.findByText('Research API 已连接');
    expect(port.getRuns.mock.calls.length).toBeGreaterThan(before);
  });

  it('ETF browsing checks Research process health without opening any research artifacts', async () => {
    const port = emptyResearch();
    const capabilities = vi.fn(port.getCapabilities);
    const status = vi.fn(port.getResearchStatus);
    await renderApp('/etf-quant/health', { ...port, getCapabilities: capabilities, getResearchStatus: status });
    await screen.findByRole('heading', { name: 'ETF Quant 数据健康' });
    expect(capabilities).not.toHaveBeenCalled();
    expect(status).not.toHaveBeenCalled();
    expect(port.getRuns).not.toHaveBeenCalled();
    expect(within(screen.getByRole('region', { name: '控制台服务' })).getAllByText('READY')).toHaveLength(3);
  });

  for (const [code, state] of [['UNREACHABLE', 'DISCONNECTED'], ['INTEGRITY_BLOCKED', 'DEGRADED']] as const) {
    it(`shows ETF ${state} independently from Research health`, async () => {
      setEtfQuantPortForTesting({
        async getStatus() { throw new EtfQuantDataError(code); },
        async getSnapshot() { throw new EtfQuantDataError(code); },
        async getReadiness() { throw new EtfQuantDataError(code); },
      });
      await renderApp('/', emptyResearch());
      await screen.findByText('Research API 已连接');
      expect(within(screen.getByRole('region', { name: '控制台服务' })).getByText(state)).toBeInTheDocument();
    });
  }
});

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { renderApp } from './test-utils';
import type { ResearchDataPort } from '@/api/contracts';
import { ResearchApiError } from '@/api/errors';
import { ErrorState } from '@/components/ui/states';

function failingPort(): ResearchDataPort {
  const reject = () => Promise.reject(new ResearchApiError('NETWORK_UNREACHABLE'));
  return {
    getHealth: reject,
    getCapabilities: reject,
    getResearchStatus: reject,
    getRuns: reject,
    getRun: reject,
    getCandidates: reject,
    getMetrics: reject,
    getDailyMetrics: reject,
    getPredictions: reject,
    getDiagnostics: reject,
    getIntegrity: reject,
  };
}

describe('API disconnected state', () => {
  it('shows a clear disconnected message instead of a blank page or console error', async () => {
    await renderApp('/', failingPort());
    expect(await screen.findByText('研究数据接口未连接')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重试连接/ })).toBeInTheDocument();
  });

  it('never renders raw error stacks in the UI', async () => {
    await renderApp('/', failingPort());
    await screen.findByText('研究数据接口未连接');
    expect(screen.queryByText(/at Object\.|at async|\.tsx?:\d+/)).toBeNull();
  });
});

describe('API error details', () => {
  it('keeps a safe BAD_QUERY detail below the Chinese explanation and raw code', () => {
    render(<ErrorState error={new ResearchApiError('BAD_QUERY',
      'date must be a valid YYYY-MM-DD', 400)} />);
    expect(screen.getByText(/查询参数无效/)).toBeInTheDocument();
    expect(screen.getByText('接口说明：date must be a valid YYYY-MM-DD')).toBeInTheDocument();
    expect(screen.getByText('错误代码：BAD_QUERY')).toBeInTheDocument();
  });
});

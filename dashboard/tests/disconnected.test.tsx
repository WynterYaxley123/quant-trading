import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from './test-utils';
import type { ResearchDataPort } from '@/api/contracts';
import { ResearchApiError } from '@/api/errors';

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
    expect(await screen.findByText('API disconnected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry connection/i })).toBeInTheDocument();
  });

  it('never renders raw error stacks in the UI', async () => {
    await renderApp('/', failingPort());
    await screen.findByText('API disconnected');
    expect(screen.queryByText(/at Object\.|at async|\.tsx?:\d+/)).toBeNull();
  });
});

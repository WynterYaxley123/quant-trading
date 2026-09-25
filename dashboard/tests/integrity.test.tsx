import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Research Integrity page', () => {
  it('shows the research definition and protocol constants', async () => {
    await renderApp('/integrity');
    expect(await screen.findByText('Research definition')).toBeInTheDocument();
    expect(screen.getByText('MOCK_SYNTHETIC_RESEARCH_LABEL')).toBeInTheDocument();
    expect(screen.getByText('Classification admission')).toBeInTheDocument();
    expect(screen.getByText('MOCK_FIXED_CLASSIFICATION')).toBeInTheDocument();
    expect(screen.getByText('Feature count')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('0.05')).toBeInTheDocument();
    expect(screen.getByText('Fusion weights')).toBeInTheDocument();
    expect(screen.getByText('0.30 / 0.40 / 0.30')).toBeInTheDocument();
  });

  it('shows status flags: development active, validation and OOS sealed, disabled execution', async () => {
    await renderApp('/integrity');
    expect(await screen.findByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getAllByText('SEALED').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Strict PIT')).toBeInTheDocument();
    expect(screen.getAllByText('DISABLED').length).toBeGreaterThanOrEqual(3);
  });

  it('abbreviates hashes and expands the full value on click', async () => {
    await renderApp('/integrity');
    expect(await screen.findByText('Artifact hashes')).toBeInTheDocument();

    const abbreviated = await screen.findAllByText('mock-split…');
    expect(abbreviated.length).toBeGreaterThanOrEqual(1);
    await userEvent.click(abbreviated[0] as HTMLElement);
    expect(
      await screen.findByText('mock-split-policy-hash-synthetic-0000000000000000000000'),
    ).toBeInTheDocument();
  });
});

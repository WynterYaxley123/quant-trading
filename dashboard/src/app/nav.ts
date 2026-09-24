import type { Capabilities } from '@/api/contracts';

/**
 * Navigation model. V1 contains research sections only — no Portfolio,
 * Orders, Trading, Execution, Account, Broker, ETF or P&L entries.
 * Future sections are documented in docs/architecture.md, not faked in the UI.
 */

export interface NavItem {
  to: string;
  label: string;
  /** Capability flag gating visibility (from /capabilities). */
  capability?: keyof Capabilities;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [{ to: '/', label: 'Overview' }],
  },
  {
    label: 'Research',
    items: [
      { to: '/candidates', label: 'Candidate Comparison', capability: 'candidateComparison' },
      { to: '/development', label: 'Development Explorer', capability: 'developmentExplorer' },
      { to: '/sectors', label: 'Sector Explorer', capability: 'sectorExplorer' },
    ],
  },
  {
    label: 'Diagnostics',
    items: [{ to: '/diagnostics', label: 'Diagnostics', capability: 'diagnostics' }],
  },
  {
    label: 'Research Integrity',
    items: [{ to: '/integrity', label: 'Research Integrity' }],
  },
];

export function visibleNavGroups(capabilities: Capabilities | null): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => {
      if (!item.capability) return true;
      // Fail open on the loading state: show items until capabilities arrive,
      // then respect them.
      return capabilities ? capabilities[item.capability] === true : true;
    }),
  })).filter((group) => group.items.length > 0);
}

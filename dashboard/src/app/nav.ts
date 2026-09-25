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
    label: '概览',
    items: [{ to: '/', label: '概览' }],
  },
  {
    label: '研究',
    items: [
      { to: '/candidates', label: '候选方案对比', capability: 'candidateComparison' },
      { to: '/development', label: 'Development 探索', capability: 'developmentExplorer' },
      { to: '/sectors', label: '行业探索', capability: 'sectorExplorer' },
    ],
  },
  {
    label: '诊断',
    items: [{ to: '/diagnostics', label: '诊断', capability: 'diagnostics' }],
  },
  {
    label: '研究完整性',
    items: [{ to: '/integrity', label: '研究完整性' }],
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

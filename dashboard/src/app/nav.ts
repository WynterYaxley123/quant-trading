import type { Capabilities } from '@/api/contracts';

/**
 * The original Research navigation stays a separate, stable contract.
 * ETF Quant is independently admitted by its own read-only API capability.
 */

export interface NavItem {
  to: string;
  label: string;
  /** Capability flag gating visibility (from /capabilities). */
  capability?: keyof Capabilities | 'etfQuant';
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: '概览',
    items: [{ to: '/', label: 'Industry Forecast' }, { to: '/research', label: '概览' }],
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

export const ETF_QUANT_NAV_GROUP: NavGroup = {
  label: '历史 ETF 产品化',
  items: [
    {to:'/etf-quant/overview',label:'总览',capability:'etfQuant'},
    {to:'/etf-quant/readiness',label:'Shadow 准备',capability:'etfQuant'},
    {to:'/etf-quant/portfolio',label:'模拟持仓',capability:'etfQuant'},
    {to:'/etf-quant/rankings',label:'行业排名',capability:'etfQuant'},
    {to:'/etf-quant/factors',label:'因子系数',capability:'etfQuant'},
    {to:'/etf-quant/mappings',label:'映射准入',capability:'etfQuant'},
    {to:'/etf-quant/trades',label:'模拟流水',capability:'etfQuant'},
    {to:'/etf-quant/benchmarks',label:'基准 CSI300',capability:'etfQuant'},
    {to:'/etf-quant/health',label:'数据健康',capability:'etfQuant'},
  ],
};

export function visibleNavGroups(capabilities: Capabilities | null, etfQuant=false): NavGroup[] {
  const groups = etfQuant
    ? [...NAV_GROUPS.slice(0, 2), ETF_QUANT_NAV_GROUP, ...NAV_GROUPS.slice(2)]
    : NAV_GROUPS;
  return groups.map((group) => ({
    ...group,
    items: group.items.filter((item) => {
      if (!item.capability) return true;
      if (item.capability==='etfQuant') return etfQuant;
      // Fail open on the loading state: show items until capabilities arrive,
      // then respect them.
      return capabilities ? capabilities[item.capability] === true : true;
    }),
  })).filter((group) => group.items.length > 0);
}

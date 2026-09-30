/**
 * Unified number / value formatting.
 *
 * Units are a correctness concern in this dashboard:
 * - RankIC / IC values are unitless — shown as plain decimals (e.g. -0.0682)
 * - Return values (spread, forward returns) are returns — shown as percentages
 *   (API 0.0181 → UI 1.81%); the conversion is documented in tooltips
 * - null / NaN / Infinity always render as the em-dash placeholder "—"
 */

export const NULL_PLACEHOLDER = '—';

export type MetricKind = 'unitless' | 'return' | 'count' | 'factor';

export function isDisplayableNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** Core formatter: safe against null / NaN / Infinity / undefined. */
export function formatMetric(value: number | null | undefined, kind: MetricKind): string {
  if (!isDisplayableNumber(value)) return NULL_PLACEHOLDER;
  switch (kind) {
    case 'unitless':
      return value.toFixed(4);
    case 'return':
      return `${(value * 100).toFixed(2)}%`;
    case 'count':
      return new Intl.NumberFormat('zh-CN').format(Math.trunc(value));
    case 'factor':
      return value.toFixed(2);
  }
}

/** IC / RankIC — unitless, 4 decimals, never percentage. */
export function formatUnitless(value: number | null | undefined): string {
  return formatMetric(value, 'unitless');
}

/** Returns — decimal input, percentage display (0.0181 → "1.81%"). */
export function formatReturn(value: number | null | undefined): string {
  return formatMetric(value, 'return');
}

export function formatCount(value: number | null | undefined): string {
  return formatMetric(value, 'count');
}

/** Alpha / fusion weights etc. */
export function formatFactor(value: number | null | undefined): string {
  return formatMetric(value, 'factor');
}

/** Short human labels for metric keys. */
export const METRIC_LABELS: Record<string, string> = {
  ic: 'IC',
  rankIc: 'RankIC',
  top5ForwardReturn: 'Top5 未来收益',
  universeForwardReturn: '行业整体未来收益',
  top5MinusUniverse: 'Top5 相对行业整体超额',
};

/** Which formatter a metric key requires (unit discipline). */
export const METRIC_KINDS: Record<string, MetricKind> = {
  ic: 'unitless',
  rankIc: 'unitless',
  top5ForwardReturn: 'return',
  universeForwardReturn: 'return',
  top5MinusUniverse: 'return',
  weightedRankIc: 'unitless',
  weightedSpread: 'return',
};

export function formatByKind(key: string, value: number | null | undefined): string {
  return formatMetric(value, METRIC_KINDS[key] ?? 'unitless');
}

export function metricUnitDescription(key: string): string {
  return (METRIC_KINDS[key] ?? 'unitless') === 'return'
    ? '收益率：API 保留小数，界面显示百分比（0.0181 → 1.81%）。'
    : '无量纲相关性指标：显示小数，不转换为百分比。';
}

/**
 * ETF Quant 数值格式化。所有数字来自独立只读 API；null / undefined /
 * NaN / Infinity 一律渲染为「—」，绝不把原始空值直接抛给用户。
 * 涨跌语义：A 股惯例 红涨绿跌，仅用于带正负号的数值，与状态徽章色相分离。
 */

export const EMPTY = '—';

function finite(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** 通用数字：千分位，最多 digits 位小数（不补零）。 */
export function fmtNum(value: number | null | undefined, digits = 4): string {
  if (!finite(value)) return EMPTY;
  return value.toLocaleString('zh-CN', { maximumFractionDigits: digits });
}

/** 整数计数：千分位。 */
export function fmtCount(value: number | null | undefined): string {
  if (!finite(value)) return EMPTY;
  return Math.trunc(value).toLocaleString('zh-CN');
}

/** API 的十进制金额字符串（CNY）。 */
export function fmtMoney(value: string | null | undefined): string {
  if (value === null || value === undefined) return EMPTY;
  const num = Number(value);
  if (!Number.isFinite(num)) return EMPTY;
  return num.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 2 });
}

/** 小数比率 → 百分比（0.0181 → 1.81%）。 */
export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (!finite(value)) return EMPTY;
  return `${(value * 100).toFixed(digits)}%`;
}

/** 带符号百分比：正数显式 +。 */
export function fmtSignedPct(value: number | null | undefined, digits = 2): string {
  if (!finite(value)) return EMPTY;
  const pct = (value * 100).toFixed(digits);
  return value > 0 ? `+${pct}%` : `${pct}%`;
}

/** 带符号系数 / 无量纲数：正数显式 +，最多 digits 位小数。 */
export function fmtSigned(value: number | null | undefined, digits = 6): string {
  if (!finite(value)) return EMPTY;
  const text = value.toLocaleString('zh-CN', { maximumFractionDigits: digits });
  return value > 0 ? `+${text}` : text;
}

/** 涨跌着色 class：红涨绿跌；零 / 空值保持中性。 */
export function gainLossClass(value: number | null | undefined): string {
  if (!finite(value) || value === 0) return 'text-foreground';
  return value > 0 ? 'text-gain' : 'text-loss';
}

/** 截断长哈希之外的通用空值兜底。 */
export function fmtText(value: string | null | undefined): string {
  return value === null || value === undefined || value === '' ? EMPTY : value;
}

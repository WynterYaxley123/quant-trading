import type { ColumnDef } from '@tanstack/react-table';
import type { ReactNode } from 'react';
import { EMPTY, fmtMoney, fmtNum, fmtPct, fmtSigned, fmtSignedPct, gainLossClass } from '../format';
import { cn } from '@/lib/cn';

/**
 * ETF 表格列定义助手：数值右对齐 + tabular-nums，代码 / 哈希用等宽字体，
 * 合理精度（不做 15 位小数直出），空值一律「—」。
 */

export type Row = Record<string, unknown>;

export type ColKind = 'text' | 'code' | 'num' | 'int' | 'money' | 'pct' | 'signed' | 'signedPct' | 'signedMoney';

export interface Col {
  key: string;
  header: string;
  kind?: ColKind;
}

function asNumber(raw: unknown): number | null {
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : null;
  if (typeof raw === 'string' && raw !== '') {
    const num = Number(raw);
    return Number.isFinite(num) ? num : null;
  }
  return null;
}

function render(kind: ColKind, raw: unknown): ReactNode {
  if (raw === null || raw === undefined) return <span className="text-muted-foreground">{EMPTY}</span>;
  switch (kind) {
    case 'code':
      return <span className="font-mono text-xs">{String(raw)}</span>;
    case 'num':
      return <span className="tabular-nums">{fmtNum(asNumber(raw))}</span>;
    case 'int':
      return <span className="tabular-nums">{fmtNum(asNumber(raw), 0)}</span>;
    case 'money':
      return <span className="tabular-nums">{fmtMoney(raw as string | null)}</span>;
    case 'pct':
      return <span className="tabular-nums">{fmtPct(asNumber(raw))}</span>;
    case 'signed': {
      // 系数等非损益数值：只加符号，不着涨跌色（涨跌色只属于真实损益）。
      const num = asNumber(raw);
      return <span className="tabular-nums">{fmtSigned(num)}</span>;
    }
    case 'signedPct': {
      const num = asNumber(raw);
      return <span className={cn('tabular-nums', gainLossClass(num))}>{fmtSignedPct(num)}</span>;
    }
    case 'signedMoney': {
      const num = asNumber(raw);
      return <span className={cn('tabular-nums', gainLossClass(num))}>{fmtMoney(raw as string | null)}</span>;
    }
    default:
      return String(raw);
  }
}

const RIGHT_ALIGNED: ReadonlySet<ColKind> = new Set(['num', 'int', 'money', 'pct', 'signed', 'signedPct', 'signedMoney']);

export function buildColumns(cols: Col[]): ColumnDef<Row, unknown>[] {
  return cols.map(({ key, header, kind = 'text' }) => ({
    accessorKey: key,
    header: RIGHT_ALIGNED.has(kind)
      ? () => <span className="block text-right">{header}</span>
      : header,
    cell: (ctx) => (
      <span className={cn('block', RIGHT_ALIGNED.has(kind) && 'text-right')}>
        {render(kind, ctx.getValue())}
      </span>
    ),
  }));
}

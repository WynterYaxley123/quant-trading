import type { EtfQuantSnapshot } from '../contracts';
import { SectionCard } from '../components/Section';
import { buildColumns, type Row } from '../components/etable';
import { DataTable } from '@/components/tables/DataTable';

const TRADE_COLUMNS = buildColumns([
  { key: 'asset_id', header: 'ETF', kind: 'code' },
  { key: 'side', header: '方向' },
  { key: 'quantity', header: '数量', kind: 'int' },
  { key: 'reference_open', header: '真实开盘价', kind: 'money' },
  { key: 'price', header: '含滑点价格', kind: 'money' },
  { key: 'commission', header: '佣金', kind: 'money' },
  { key: 'slippage', header: '滑点披露', kind: 'money' },
  { key: 'stamp_duty', header: '印花税', kind: 'money' },
  { key: 'signal', header: 'T0 信号日' },
  { key: 'execution', header: 'T+1 执行日' },
  { key: 'total_cash_impact', header: '现金影响 CNY', kind: 'signedMoney' },
  { key: 'rebalance_reason', header: '重平衡原因' },
  { key: 'market_execution_at', header: '市场开盘时间' },
  { key: 'processed_at', header: '实际处理时间' },
]);

/**
 * 模拟成交流水：T0 意图先持久化；T+1 真实开盘价，收盘后延迟记账。
 * market_execution_at 与 processed_at 分开披露。这些是模拟账户的
 * 记账记录，不是券商订单，也不存在任何下单入口。
 */
export function TradesSection({ data }: { data: EtfQuantSnapshot }) {
  const rows = data.trades.map((t) => ({
    ...t,
    asset_id: t.intent.asset_id,
    side: t.intent.side,
    quantity: t.intent.quantity,
    signal: t.intent.signal_session,
    execution: t.intent.execution_session,
  }));
  return (
    <SectionCard
      title="Forward-only 模拟成交"
      description="T0 意图先持久化；T+1 真实开盘价，收盘后延迟记账。market_execution_at 与 processed_at 分开披露；以下为模拟记账记录，不是券商订单。"
    >
      <DataTable data={rows as Row[]} columns={TRADE_COLUMNS} caption="模拟成交记录（不是券商订单）" manualSorting />
    </SectionCard>
  );
}

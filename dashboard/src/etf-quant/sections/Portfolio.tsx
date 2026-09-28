import type { EtfQuantSnapshot } from '../contracts';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { SectionCard } from '../components/Section';
import { buildColumns, type Row } from '../components/etable';
import { NavChart } from './NavChart';
import { DataTable } from '@/components/tables/DataTable';
import { EmptyState } from '@/components/ui/states';
import { fmtCount, fmtMoney, fmtNum, fmtPct, fmtSignedPct, fmtText, gainLossClass } from '../format';

const HOLDING_COLUMNS = buildColumns([
  { key: 'asset_id', header: 'ETF', kind: 'code' },
  { key: 'etf_name', header: 'ETF 名称' },
  { key: 'industry_name', header: '行业' },
  { key: 'quantity', header: '数量', kind: 'int' },
  { key: 'average_cost', header: '平均成本', kind: 'money' },
  { key: 'mark_price', header: '最新 finalized close', kind: 'money' },
  { key: 'market_value', header: '市值 CNY', kind: 'money' },
  { key: 'weight', header: '持仓权重（上限 35%）', kind: 'pct' },
  { key: 'unrealized_pnl', header: '未实现损益', kind: 'signedMoney' },
  { key: 'unrealized_return', header: '未实现收益率', kind: 'signedPct' },
]);

/**
 * 模拟持仓组合。无 epoch 时是单一诚实空态：不渲染任何账户指标、
 * 持仓或 NAV —— 历史模型预热不会生成账户收益。
 */
export function PortfolioSection({ data }: { data: EtfQuantSnapshot }) {
  if (!data.status.epoch) {
    return (
      <EmptyState
        title="Shadow 尚未启动"
        description="没有 epoch，因此没有持仓、模拟成交或 NAV。历史模型预热不会生成账户收益。"
      />
    );
  }
  const s = data.portfolio_summary;
  return (
    <>
      <MetricGrid className="xl:grid-cols-4">
        <MetricCard label="当前总资产（CNY）" value={fmtMoney(s.total_equity)} hint={`初始资金 ${fmtMoney(s.initial_cash)}`} />
        <MetricCard label="现金（CNY）" value={fmtMoney(s.cash)} />
        <MetricCard label="持仓市值（CNY）" value={fmtMoney(s.market_value)} />
        <MetricCard label="epoch 总收益" value={fmtSignedPct(s.total_return)} valueClassName={gainLossClass(s.total_return)} />
        <MetricCard label="最大回撤" value={fmtPct(s.max_drawdown)} />
        <MetricCard label="Sharpe" value={fmtNum(s.sharpe)} hint="forward epoch 内，无量纲" />
        <MetricCard label="已实现损益" value={fmtMoney(s.realized_pnl)} />
        <MetricCard label="未实现损益" value={fmtMoney(s.unrealized_pnl)} />
        <MetricCard label="总损益 CNY" value={fmtMoney(s.total_pnl)} />
        <MetricCard label="forward 日收益" value={fmtSignedPct(s.daily_return)} valueClassName={gainLossClass(s.daily_return)} />
        <MetricCard label="累计换手 / 初始资金" value={fmtPct(s.turnover)} hint="含滑点成交名义额 ÷ 初始资金" />
        <MetricCard
          label="重平衡"
          value={`${fmtCount(s.rebalance_count)} 次`}
          hint={`最近重平衡 ${fmtText(s.last_rebalance_at)} · 仅当可执行 ETF 集合变化时触发`}
        />
      </MetricGrid>

      <SectionCard
        title="最新模拟持仓"
        description="单一行业目标权重上限 35%；数量按 lot size 取整；全部为模拟账户头寸，非真实持仓。"
      >
        <DataTable
          data={data.holdings as Row[]}
          columns={HOLDING_COLUMNS}
          caption="当前 shadow 模拟持仓"
          manualSorting
          rowClassName={(row) => (Number(row.original.weight) >= data.strategy.target_weight_cap ? 'bg-warning/10' : undefined)}
        />
      </SectionCard>

      <NavChart data={data} />
    </>
  );
}

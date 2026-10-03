import type { EtfQuantSnapshot } from '../contracts';
import { SectionCard } from '../components/Section';
import { buildColumns, type Row } from '../components/etable';
import { DataTable } from '@/components/tables/DataTable';

const ENTRY_COLUMNS = buildColumns([
  { key: 'industry_code', header: '行业', kind: 'code' },
  { key: 'etf_code', header: 'ETF', kind: 'code' },
  { key: 'etf_name', header: '名称' },
  { key: 'tracking_index_code', header: '跟踪指数', kind: 'code' },
  { key: 'mapping_method', header: '证据方法' },
  { key: 'verification_status', header: '核验' },
  { key: 'effective_from', header: '生效' },
  { key: 'effective_to', header: '结束' },
  { key: 'mean_amount_cny', header: '20 日平均成交额 CNY', kind: 'num' },
]);

const DIAGNOSTIC_COLUMNS = buildColumns([
  { key: 'industry_level', header: '行业层级' },
  { key: 'industry_code', header: '行业', kind: 'code' },
  { key: 'etf_code', header: 'ETF', kind: 'code' },
  { key: 'verification_status', header: '状态' },
  { key: 'liquidity_sessions', header: '完整交易日', kind: 'int' },
  { key: 'mean_amount_cny', header: '真实平均成交额 CNY', kind: 'num' },
  { key: 'reason', header: '阻断原因' },
]);

const B40_SLOT_COLUMNS = buildColumns([
  { key: 'industry_rank', header: 'Rank', kind: 'int' },
  { key: 'industry_code', header: '原 Top5 行业', kind: 'code' },
  { key: 'mapping_type', header: '执行类型' },
  { key: 'etf_code', header: 'ETF / Cash', kind: 'code' },
  { key: 'target_l2_exposure', header: 'Proxy 目标 L2 占比', kind: 'pct' },
  { key: 'evidence_available_at', header: 'Evidence available at' },
  { key: 'liquidity_status', header: '20 日流动性' },
  { key: 'target_weight', header: '原目标权重', kind: 'num' },
  { key: 'cash_retained_weight', header: '保留 Cash', kind: 'num' },
  { key: 'execution_reason', header: '执行说明' },
]);

/**
 * ETF 映射准入：只接受 VERIFIED + A_SHARE_INDUSTRY_OR_THEME_ETF，
 * 要求 20 个完整交易日的真实成交额（CNY）与非零 volume；
 * 不按名字猜测，不倒填映射历史。BLOCKED 原因必须显式可见。
 */
export function MappingsSection({ data }: { data: EtfQuantSnapshot }) {
  if (data.strategy.execution_policy === 'B40_WITH_CASH') return (
    <>
      <SectionCard title="40% 行业敞口代理与现金回退 · 只读执行映射"
        description="按原前五行业排名逐槽显示直接跟踪 / 行业代理 / 现金；证据不足或流动性不合格时保留原权重为现金。兼容标识 B40_WITH_CASH。现金不是 ETF，也不会产生订单。">
        <p className="text-sm">信号目标风险资产：{data.mappings.risk_asset_weight ?? '—'} · 目标保留 Cash：{data.mappings.cash_weight ?? '—'} · 实际账户现金以持仓页为准；Shadow 状态以正式 readiness 记录为准。</p>
        <DataTable data={(data.mappings.slots ?? []).map(s=>({...s,etf_code:s.etf_code??'CASH / FAIL-CLOSED'})) as Row[]} columns={B40_SLOT_COLUMNS} caption="PIT 执行槽（含 Cash）" manualSorting />
      </SectionCard>
      <SectionCard title="行业代理准入诊断" description="只读显示证据与流动性判定；历史工程参考不等于当前可执行映射。">
        <DataTable data={data.mappings.diagnostics as Row[]} columns={DIAGNOSTIC_COLUMNS} caption="PIT 候选诊断" manualSorting />
      </SectionCard>
    </>
  );
  return (
    <>
      <SectionCard
        title={<span className="font-mono">{data.mappings.status}</span>}
        description={`生产行业层级：${data.mappings.industry_level ?? data.strategy.industry_level}（申万 2021 二级，4 位代码）。只接受 VERIFIED + A_SHARE_INDUSTRY_OR_THEME_ETF；要求 ${data.mappings.liquidity_sessions ?? data.strategy.liquidity_sessions} 个完整交易日的真实 amount（CNY）与非零 volume；不按名字猜测，不倒填映射历史。`}
      >
        <p className="text-sm">{data.mappings.reason ?? '准入说明未提供；不可据此推断已有五个独立、已验证 ETF。'}</p>
        <DataTable data={data.mappings.entries as Row[]} columns={ENTRY_COLUMNS} caption="已准入 ETF 映射" manualSorting />
      </SectionCard>
      <SectionCard title="准入阻断 / candidate diagnostics" description="每一行都是一个被阻断的候选及其原因；阻断是准入机制的正常输出，不是系统故障。">
        <DataTable data={data.mappings.diagnostics as Row[]} columns={DIAGNOSTIC_COLUMNS} caption="映射准入诊断" manualSorting />
      </SectionCard>
    </>
  );
}

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
  { key: 'industry_code', header: '行业', kind: 'code' },
  { key: 'etf_code', header: 'ETF', kind: 'code' },
  { key: 'verification_status', header: '状态' },
  { key: 'liquidity_sessions', header: '完整交易日', kind: 'int' },
  { key: 'mean_amount_cny', header: '真实平均成交额 CNY', kind: 'num' },
  { key: 'reason', header: '阻断原因' },
]);

/**
 * ETF 映射准入：只接受 VERIFIED + A_SHARE_INDUSTRY_OR_THEME_ETF，
 * 要求 20 个完整交易日的真实成交额（CNY）与非零 volume；
 * 不按名字猜测，不倒填映射历史。BLOCKED 原因必须显式可见。
 */
export function MappingsSection({ data }: { data: EtfQuantSnapshot }) {
  return (
    <>
      <SectionCard
        title={<span className="font-mono">{data.mappings.status}</span>}
        description="只接受 VERIFIED + A_SHARE_INDUSTRY_OR_THEME_ETF。20 个完整交易日真实 amount（CNY）/ 非零 volume；不按名字猜测，不倒填映射历史。"
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

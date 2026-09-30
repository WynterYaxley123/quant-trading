import { Link } from '@tanstack/react-router';
import type { EtfQuantReadiness, EtfQuantSnapshot } from '../contracts';
import { useResource, type ResourceState } from '@/hooks/useResource';
import { getEtfQuantPort } from '../data-port';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { PhaseBadge, StatusBadge } from '../components/StatusBadge';
import { SectionCard } from '../components/Section';
import { ReadinessBanner } from '../components/ReadinessGates';
import { Skeleton } from '@/components/ui/skeleton';
import { fmtMoney, fmtText } from '../format';
import { CurrentStatusResource } from '../components/CurrentStatus';

function readinessTone(readiness: EtfQuantReadiness): 'success' | 'destructive' | 'muted' {
  return readiness.overall === 'PASS' ? 'success' : readiness.overall === 'BLOCKED' ? 'destructive' : 'muted';
}

/** Shadow 准备状态摘要：来自独立的 getReadiness()，失败时诚实降级，不阻断总览。 */
function ReadinessSummary({ readiness }: { readiness: ResourceState<EtfQuantReadiness> }) {
  if (readiness.loading) {
    return <Skeleton className="h-20 w-full" aria-label="正在读取 Shadow 准备状态" />;
  }
  if (readiness.error || !readiness.data) {
    return (
      <p className="text-sm text-muted-foreground" role="alert">
        Shadow 准备状态接口未连接，本区块暂缺评估结果；其余区块不受影响。
      </p>
    );
  }
  const data = readiness.data;
  const counts = { PASS: 0, BLOCKED: 0, NOT_REACHED: 0, DEFERRED: 0, UNKNOWN: 0 };
  for (const gate of data.gates) counts[gate.status] += 1;
  return (
    <div className="flex flex-col gap-3">
      <ReadinessBanner readiness={data} />
      {data.gates.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          门控 {data.gates.length} 项：通过 {counts.PASS} · 阻断 {counts.BLOCKED} · 暂缓 {counts.DEFERRED} · 未达成 {counts.NOT_REACHED}
          {counts.UNKNOWN ? ` · 未知 ${counts.UNKNOWN}` : ''}
        </p>
      ) : null}
      <Link to="/etf-quant/readiness" className="w-fit text-sm font-medium text-primary underline-offset-4 hover:underline">
        查看完整启动门控清单 →
      </Link>
    </div>
  );
}

function ReadinessKpi({ readiness }: { readiness: ResourceState<EtfQuantReadiness> }) {
  if (readiness.loading) return <>评估中…</>;
  if (readiness.data) return <StatusBadge status={readiness.data.overall} />;
  return <span className="text-sm font-normal text-muted-foreground">接口未连接</span>;
}

/**
 * 总览首屏回答四个问题：系统现在能不能跑、数据最新到哪天、
 * Shadow 准备状态、候选 / 映射 / 流动性状态。工程溯源在状态条内折叠。
 */
export function OverviewSection({ data }: { data: EtfQuantSnapshot }) {
  const port = getEtfQuantPort();
  const readiness = useResource((signal) => port.getReadiness(signal), [port]);
  return (
    <>
      {port.getCurrentStatus ? <CurrentStatusResource /> : <><MetricGrid>
        <MetricCard label="运行阶段" value={<PhaseBadge phase={data.status.phase} />} hint={fmtText(data.status.reason)} />
        <MetricCard label="数据截止日" value={fmtText(data.status.cutoff)} hint={`最近更新 ${fmtText(data.status.updated_at)}`} />
        <MetricCard
          label="Shadow 准备状态"
          tone={readiness.data ? readinessTone(readiness.data) : 'default'}
          value={<ReadinessKpi readiness={readiness} />}
          hint="SHADOW_START_READINESS_V1"
        />
        <MetricCard
          label="映射准入 / 流动性"
          tone={data.mappings.status.includes('BLOCKED') ? 'destructive' : data.mappings.status.includes('ADMITTED') || data.mappings.status === 'OK' ? 'success' : 'default'}
          value={<span className="break-all font-mono text-sm">{data.mappings.status}</span>}
          hint={data.mappings.reason ?? '准入说明未提供；不可据此推断映射或流动性已通过。'}
        />
        <MetricCard
          label="基准 CSI 300"
          tone={data.benchmark.status.includes('BLOCKED') ? 'destructive' : 'default'}
          value={<span className="font-mono text-sm">{data.benchmark.status}</span>}
          hint="NASDAQ / S&P 500 暂缓接入"
        />
        <MetricCard
          label="运行健康"
          tone={data.health.status === 'DEGRADED' || data.health.status.includes('BLOCKED') ? 'destructive' : data.health.status === 'OK' ? 'success' : 'default'}
          value={<span className="break-all font-mono text-sm">{data.health.status}</span>}
          hint={data.health.blockers.length ? data.health.blockers.join(' · ') : '无已记录阻断'}
        />
      </MetricGrid>

      <SectionCard title="Shadow 启动准备" description="只读评估：本界面不能启动 Shadow，也不能创建 epoch。">
        <ReadinessSummary readiness={readiness} />
      </SectionCard></>}

      <SectionCard title="冻结策略参数 · ETF-Quant V1" description="初始预算 CNY 10,000 · 三个独立 Ridge 模型 · Top 5 行业 · 35% 目标权重上限 · 仅在可执行 ETF 集合变化时重平衡。">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3 xl:grid-cols-5">
          <div><dt className="text-xs text-muted-foreground">佣金</dt><dd className="tabular-nums">{data.strategy.costs.commission_bps} bps</dd></div>
          <div><dt className="text-xs text-muted-foreground">滑点 / side</dt><dd className="tabular-nums">{data.strategy.costs.slippage_bps} bps</dd></div>
          <div><dt className="text-xs text-muted-foreground">印花税</dt><dd className="tabular-nums">{data.strategy.costs.stamp_duty_bps} bps</dd></div>
          <div><dt className="text-xs text-muted-foreground">最低佣金</dt><dd className="tabular-nums">{fmtMoney(data.strategy.costs.minimum_commission)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">lot size</dt><dd className="tabular-nums">{data.strategy.lot_size}</dd></div>
        </dl>
      </SectionCard>

      <SectionCard title="数据源与 Shadow 准入" description="历史数据只用于 MODEL_WARMUP / TRAINING_INPUT / ENGINEERING_VALIDATION，不能展示为历史账户业绩。">
        <p className="text-sm">
          <span className="font-mono text-xs">{data.mappings.status}</span>
          <span className="text-muted-foreground"> · {data.mappings.reason ?? '—'}</span>
        </p>
      </SectionCard>
    </>
  );
}

import type { EtfQuantCurrentStatus } from '../contracts';
import { getEtfQuantPort } from '../data-port';
import { useResource } from '@/hooks/useResource';
import { MetricCard,MetricGrid } from './MetricCard';
import { SectionCard } from './Section';
import { fmtPct,fmtText } from '../format';

export function CurrentStatusPanel({data}:{data:EtfQuantCurrentStatus}) {
  const f=data.formal;
  return <>
    <MetricGrid>
      <MetricCard label="工程状态" value={data.engineering_complete?'COMPLETE':'UNKNOWN'} />
      <MetricCard label="生产可用于 Shadow" value={String(data.production_usable).toUpperCase()} />
      <MetricCard label="数据截止日" value={fmtText(data.latest_finalized_market_date)} hint={`snapshot ${data.snapshot_id?.slice(0,12)??'—'}`} />
      <MetricCard label="模型输入准备" value={data.model_readiness.status} hint={`readiness reference as of ${fmtText(data.model_readiness.as_of)}`} />
      <MetricCard label="Shadow Runtime" value={data.shadow_runtime_armed?'ARMED':'NOT_ARMED'} />
      <MetricCard label="启动门控" value={data.shadow_start_gate} />
      <MetricCard label="下一 eligible 交易日" value={fmtText(data.calendar?.next_eligible_trading_date)} hint="动态读取正式交易日历；不承诺届时数据已 finalized" />
      <MetricCard label="交易日状态" value={data.calendar?.market_state??'UNKNOWN'} />
      <MetricCard label="Broker / Real Order Path" value="OFF / OFF" hint={`${data.mode} · READ-ONLY`} />
    </MetricGrid>
    <SectionCard title="三期限模型输入" description={`工程 readiness reference as of ${fmtText(data.model_readiness.as_of)}；不是 Formal Signal。`}>
      <dl className="grid gap-3 sm:grid-cols-3">{['10','40','120'].map(h=>{
        const row=data.model_readiness.horizons[h];
        return <div key={h}><dt>H{h} · {row?.status??'UNKNOWN'}</dt><dd className="text-sm text-muted-foreground">{row?`${row.valid_observations} observations · ${row.unique_valid_dates} dates · ${row.valid_sectors} sectors · mature ${row.mature_cutoff} · min ${row.minimum_valid_dates} dates`:'无已认证记录'}</dd></div>;
      })}</dl>
    </SectionCard>
    <SectionCard title="Formal Shadow Epoch" description="T0 正式信号与 T+1 延迟账务分别观察；未开始时不显示虚构账户资产。">
      {!f.epoch_id?<p>No Formal Shadow Epoch yet · 等待下一 eligible finalized trading cycle。</p>
        :<p>Epoch <code>{f.epoch_id}</code> · Signal {f.signal_date} · {f.t1_status}</p>}
      <p className="mt-2 text-sm text-muted-foreground">Epoch {f.epoch_count} · Signal {f.signal_count} · Intent {f.intent_count??'—'} · Fill {f.fill_count} · Holdings {f.holdings_count}</p>
      <p className="text-sm text-muted-foreground">信号目标 Cash {fmtPct(f.cash_weight)} · Risk {fmtPct(f.risk_asset_weight)} · NAV {fmtText(f.nav)} · PnL {fmtText(f.pnl)}</p>
    </SectionCard>
    <SectionCard title="最近 one-shot observation" description="只读 receipt；时间字段保留其实际来源。">
      <p>{data.runner?.status??'NOT_OBSERVED'} · {data.runner?.next_action??'—'}</p>
      <p className="text-sm text-muted-foreground">{data.runner?.observed_at} · {data.runner?.time_source} · refresh attempted {String(data.runner?.refresh_attempted??false)} · reason {fmtText(data.runner?.reason_code)}</p>
    </SectionCard>
    <SectionCard title="认证与溯源" description={`静态 release as of ${fmtText(data.release_as_of)}；动态控制状态 observed at ${data.observed_at}。`}>
      <p>PIT {data.evidence.production_pit} · Strict {data.evidence.strict_registry} · SWS {data.evidence.sws}</p>
      <p className="text-xs text-muted-foreground">{data.evidence.known_limitation}</p>
      <div className="mt-3 grid gap-1 text-xs">{Object.entries(data.provenance).map(([key,value])=><p key={key}>{key}: <code className="break-all select-all">{value??'—'}</code></p>)}</div>
      {data.historical_status?<p role="status" className="mt-3 text-sm">SUPERSEDED / HISTORICAL：{data.historical_status.reason_code} · 这是旧失败审计，不覆盖当前状态。</p>:null}
      <p className="mt-3 text-xs text-muted-foreground">SOURCE_LICENSING_UNRESOLVED · 历史分类 PIT 未证明；执行 PIT 独立 fail closed。</p>
    </SectionCard>
    {data.one_shot_command?<SectionCard title="运行下一次 Shadow cycle" description="复制到终端执行；控制台不会启动 runner，也不会修改 runtime。">
      <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded bg-muted p-3 text-xs select-all"><code>{data.one_shot_command}</code></pre>
    </SectionCard>:null}
  </>;
}

export function CurrentStatusResource() {
  const port=getEtfQuantPort();
  const resource=useResource(signal=>port.getCurrentStatus!(signal),[port]);
  if(resource.loading) return <p>正在读取 Current ETF-Quant Status…</p>;
  if(resource.error || !resource.data) return <p role="alert">Current Status 接口未连接 / 完整性阻断；不能把历史报告当作当前状态。</p>;
  return <CurrentStatusPanel data={resource.data} />;
}

import { useState } from 'react';
import { Bar,BarChart,CartesianGrid,Legend,Line,LineChart,ReferenceLine,ResponsiveContainer,Tooltip,XAxis,YAxis } from 'recharts';
import type { ColumnDef } from '@tanstack/react-table';
import { useResource } from '@/hooks/useResource';
import { ChartFrame } from '@/components/charts/ChartFrame';
import { DataTable } from '@/components/tables/DataTable';
import { StatusCard,StatusCardGrid } from '@/components/research/StatusCard';
import { HashText } from '@/components/research/HashText';
import { Card,CardContent,CardHeader,CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LoadingState,EmptyState } from '@/components/ui/states';
import { getEtfQuantPort } from './data-port';
import type { EtfQuantSnapshot } from './contracts';

export type EtfSection='overview'|'portfolio'|'rankings'|'factors'|'mappings'|'trades'|'benchmarks'|'health';
type Row=Record<string,unknown>;
const N='—';
const fmt=(value:unknown):string=>value===null || value===undefined?N:typeof value==='number'?value.toLocaleString('zh-CN',{maximumFractionDigits:6}):String(value);
const money=(value:string|null):string=>value===null?N:Number(value).toLocaleString('zh-CN',{style:'currency',currency:'CNY',maximumFractionDigits:2});
const percent=(value:number|null):string=>value===null?N:(value*100).toFixed(2)+'%';
const TITLES:Record<EtfSection,string>={overview:'ETF Quant Overview',portfolio:'Shadow Portfolio',rankings:'Industry Rankings',
  factors:'Factors & Model Coefficients',mappings:'ETF Mapping Admission',trades:'Simulated Trades',benchmarks:'CSI 300 Benchmark',health:'ETF Quant Data Health'};

function Table({rows,columns,caption,highlight=false}:{rows:Row[];columns:Array<[string,string]>;caption:string;highlight?:boolean}) {
  const defs:ColumnDef<Row,unknown>[]=columns.map(([key,header])=>({accessorKey:key,header,
    cell:ctx=><span className="tabular-nums">{fmt(ctx.getValue())}</span>}));
  return <DataTable data={rows} columns={defs} caption={caption} manualSorting rowClassName={row=>highlight && Number(row.original.rank)<=5?'bg-primary/5':undefined}/>;
}
function Box({title,children}:{title:string;children:React.ReactNode}) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-3">{children}</CardContent></Card>;
}
function Tabs<T extends string>({values,value,onChange}:{values:readonly T[];value:T;onChange:(next:T)=>void}) {
  return <div role="tablist" className="flex flex-wrap gap-2">{values.map(v=><Button key={v} role="tab" variant={v===value?'default':'outline'}
    aria-selected={v===value} onClick={()=>onChange(v)}>{v}</Button>)}</div>;
}

function Summary({s}:{s:EtfQuantSnapshot['portfolio_summary']}) {
  return <StatusCardGrid>
    <StatusCard label="当前资产（CNY）" value={money(s.total_equity)}/><StatusCard label="现金（CNY）" value={money(s.cash)}/>
    <StatusCard label="持仓市值（CNY）" value={money(s.market_value)}/><StatusCard label="epoch 总收益" value={percent(s.total_return)}/>
    <StatusCard label="最大回撤" value={percent(s.max_drawdown)}/><StatusCard label="Sharpe" value={fmt(s.sharpe)}/>
    <StatusCard label="已实现损益" value={money(s.realized_pnl)}/><StatusCard label="未实现损益" value={money(s.unrealized_pnl)}/>
    <StatusCard label="总损益 CNY" value={money(s.total_pnl)}/><StatusCard label="forward 日收益" value={percent(s.daily_return)}/>
    <StatusCard label="累计换手 / 初始资金" value={percent(s.turnover)}/>
    <StatusCard label="重平衡次数" value={fmt(s.rebalance_count)}/><StatusCard label="最近重平衡" value={fmt(s.last_rebalance_at)}/>
  </StatusCardGrid>;
}

function NAV({data}:{data:EtfQuantSnapshot}) {
  if(!data.status.epoch || !data.nav.length) return <EmptyState title="Shadow 尚未启动" description="没有 epoch，因此没有持仓、模拟成交或 NAV。历史模型预热不会生成账户收益。"/>;
  const benchmark=new Map(data.benchmark.points.map(p=>[p.trade_date,p.normalized]));
  const points=data.nav.map(p=>({date:p.trade_date,shadow:Number(p.normalized_nav),csi300:benchmark.get(p.trade_date) ?? null}));
  return <ChartFrame title="Forward NAV · CSI 300" description="同一 epoch 起点；归一化净值（无量纲）。缺口不连接，不补写历史。"
    summary={`${points.length} 个 forward epoch NAV 点；仅用于模拟账户观察。`}>
    <ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{left:4,right:16,top:12,bottom:8}}>
      <CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="date" tick={{fontSize:10}}/><YAxis domain={['auto','auto']} tick={{fontSize:11}}/>
      <Tooltip/><Legend/><Line type="linear" dataKey="shadow" name="Shadow NAV" stroke="var(--color-primary)" dot={points.length===1} connectNulls={false}/>
      <Line type="linear" dataKey="csi300" name="CSI 300" stroke="#64748b" dot={points.length===1} connectNulls={false}/>
    </LineChart></ResponsiveContainer>
  </ChartFrame>;
}

function Rankings({data}:{data:EtfQuantSnapshot}) {
  const [h,setH]=useState<'10d'|'40d'|'120d'|'fusion'>('fusion');
  const [all,setAll]=useState(false);
  const rows=data.rankings[h];
  return <Box title="10d / 40d / 120d / Fusion">
    <Tabs values={['10d','40d','120d','fusion'] as const} value={h} onChange={setH}/>
    <p className="text-sm text-muted-foreground">默认显示 Top 20，Top 5 高亮。单 horizon 为原始预测；Fusion 为各 horizon 横截面 z-score 的 0.25 / 0.50 / 0.25 加权分数。</p>
    <Button variant="outline" onClick={()=>setAll(v=>!v)}>{all?'仅显示 Top 20':'显示全部行业'}</Button>
    <p className="text-sm">{all?rows.length:Math.min(rows.length,20)} / {rows.length} 个行业</p>
    <Table rows={(all?rows:rows.slice(0,20)) as Row[]} columns={[["rank","排名"],["industry_code","行业代码（名称未解析）"],["score","预测 / Fusion 分数（无量纲）"]]} caption={`${h} 行业排名`} highlight/>
  </Box>;
}

function Factors({data}:{data:EtfQuantSnapshot}) {
  const [h,setH]=useState<'10d'|'40d'|'120d'>('10d');
  const horizon=Number(h.slice(0,-1));
  const model=data.models.find(m=>m.horizon===horizon);
  const names=horizon===10?data.strategy.h10_factors:horizon===40?data.strategy.h40_factors:data.strategy.h120_factors;
  const registry=new Map(data.strategy.factor_registry.map(f=>[f.name,f]));
  const rows=names.map((name,i)=>({name,formula:registry.get(name)?.formula,lookback:registry.get(name)?.lookback_sessions,
    coefficient:model?.coefficients[i] ?? null}));
  return <>
    <Box title="Frozen factor set / named coefficients">
      <Tabs values={['10d','40d','120d'] as const} value={h} onChange={setH}/>
      <p>Ridge α = 0.01 · 6 calendar months · label-cutoff anchor · raw X（不标准化）</p>
      <p>模型状态：{model?'READY':'MODEL_WARMUP_INCOMPLETE'} · 截距：{fmt(model?.intercept)}</p>
      <p className="break-all text-sm text-muted-foreground">训练日期：{model?.training.training_start ?? N} → {model?.training.training_end ?? N}；
        label cutoff：{model?.training.label_cutoff ?? N}；有效交易日：{fmt(model?.training.training_day_count)}；样本：{fmt(model?.training.sample_count)}</p>
      <p className="text-sm">current snapshot observed：{model?.current_snapshot_observed_at ?? N}；historical available_at：UNKNOWN / null</p>
      <HashText value={model?.model_hash ?? null}/>
      <Table rows={rows} columns={[["name","因子"],["formula","实际 close 公式"],["lookback","lookback sessions"],["coefficient","系数（有符号）"]]} caption={`${h} 因子和系数`}/>
    </Box>
    {model?<ChartFrame title={`${h} Ridge 有符号系数`} description="原始特征尺度，不跨 horizon 比较系数大小。" summary={`${names.length} 个具名 Ridge 系数。`} bodyClassName="h-[440px]">
      <ResponsiveContainer width="100%" height="100%"><BarChart data={rows} layout="vertical" margin={{left:8,right:24}}>
        <CartesianGrid strokeDasharray="3 3"/><XAxis type="number"/><YAxis type="category" dataKey="name" width={48}/><ReferenceLine x={0}/><Tooltip/>
        <Bar dataKey="coefficient" name="Ridge coefficient" fill="var(--color-primary)"/>
      </BarChart></ResponsiveContainer>
    </ChartFrame>:null}
  </>;
}

function Mappings({data}:{data:EtfQuantSnapshot}) {
  return <>
    <Box title={data.mappings.status}><p>{data.mappings.reason ?? '五个独立、已验证 ETF 已通过准入。'}</p>
      <p className="text-sm text-muted-foreground">只接受 VERIFIED + A_SHARE_INDUSTRY_OR_THEME_ETF。20 个完整交易日真实 amount（CNY）/非零 volume；不按名字猜测，不倒填映射历史。</p>
      <Table rows={data.mappings.entries as Row[]} columns={[["industry_code","行业"],["etf_code","ETF"],["etf_name","名称"],
        ["tracking_index_code","跟踪指数"],["mapping_method","证据方法"],["verification_status","核验"],["effective_from","生效"],
        ["effective_to","结束"],["mean_amount_cny","20 日平均成交额 CNY"]]} caption="已准入 ETF 映射"/>
    </Box>
    <Box title="准入阻断 / candidate diagnostics"><Table rows={data.mappings.diagnostics as Row[]} columns={[["industry_code","行业"],["etf_code","ETF"],
      ["verification_status","状态"],["liquidity_sessions","完整交易日"],["mean_amount_cny","真实平均成交额 CNY"],["reason","阻断原因"]]} caption="映射准入诊断"/></Box>
  </>;
}

function Contents({section,data}:{section:EtfSection;data:EtfQuantSnapshot}) {
  if(section==='rankings') return <Rankings data={data}/>;
  if(section==='factors') return <Factors data={data}/>;
  if(section==='mappings') return <Mappings data={data}/>;
  if(section==='trades') return <Box title="Forward-only simulated fills"><p className="text-sm">T0 意图先持久化；T+1 真实开盘价，收盘后延迟记账。market_execution_at 与 processed_at 分开披露。</p>
    <Table rows={data.trades.map(t=>({...t,asset_id:t.intent.asset_id,side:t.intent.side,quantity:t.intent.quantity,signal:t.intent.signal_session,
      execution:t.intent.execution_session}))} columns={[["asset_id","ETF"],["side","BUY / SELL"],["quantity","数量"],["reference_open","真实开盘价"],
      ["price","含滑点价格"],["commission","佣金"],["slippage","滑点披露"],["stamp_duty","印花税"],["signal","T0"],["execution","T+1"],
      ["total_cash_impact","现金影响 CNY"],["rebalance_reason","重平衡原因"],
      ["market_execution_at","市场开盘时间"],["processed_at","实际处理时间"]]} caption="模拟成交记录（不是券商订单）"/></Box>;
  if(section==='benchmarks') return <><Box title="CSI 300 · 000300.SH"><p>仅使用 sidecar 的 CSI 300 导出，epoch 起点归一化。基准不进入模型、行业排名或仓位。</p>
    <p>NASDAQ Composite：DEFERRED · S&amp;P 500：DEFERRED</p></Box><NAV data={data}/></>;
  if(section==='health') return <>
    <StatusCardGrid><StatusCard label="运行健康" value={data.health.status}/><StatusCard label="快照新鲜度" value={fmt(data.health.freshness)}/>
      <StatusCard label="exact adjustment rows" value={fmt(data.health.adjustment_exact_rows)}/><StatusCard label="rejected adjustment rows" value={fmt(data.health.adjustment_rejected_rows)}/>
      <StatusCard label="strict TLS" value={data.health.strict_tls}/></StatusCardGrid>
    <Box title="质量与阻断"><p>{data.health.blockers.join(' · ') || '无已记录阻断'}</p><p>{data.health.quality_flags.join(' · ')}</p>
      <p>非官方行业指数；历史分类不是 ex-ante PIT 证据。available_at / source_published_at = UNKNOWN / null。</p>
      <Table rows={(data.health.coverage ?? []) as Row[]} columns={[["industry_code","行业"],["trade_date","日期"],["status","状态"],
        ["eligible_members","eligible members"],["valid_constituents","valid constituents"],["coverage","coverage ratio"],["reason","原因"]]} caption="行业成分覆盖"/></Box>
  </>;
  return <>
    {section==='overview'?<Box title="Frozen ETF-Quant V1"><p>初始预算 CNY 10,000 · 三个独立 Ridge · Top5 · 35% target cap · 只在可执行 ETF 集合变化时重平衡。</p>
      <p>佣金 {data.strategy.costs.commission_bps} bps，滑点 {data.strategy.costs.slippage_bps} bps / side；印花税 {data.strategy.costs.stamp_duty_bps} bps；
        最低佣金 {data.strategy.costs.minimum_commission} CNY；lot size {data.strategy.lot_size}。</p></Box>:null}
    <Summary s={data.portfolio_summary}/><NAV data={data}/>
    <Box title="当前模拟持仓"><Table rows={data.holdings as Row[]} columns={[["asset_id","ETF"],["etf_name","ETF 名称"],["industry_name","行业"],
      ["quantity","数量"],["average_cost","平均成本"],["mark_price","最新 finalized close"],["market_value","市值 CNY"],
      ["weight","持仓权重"],["unrealized_pnl","未实现损益"],["unrealized_return","未实现收益率"]]} caption="当前 shadow 持仓"/></Box>
    {section==='overview'?<Box title="Source & Shadow admission"><p>{data.mappings.status} · {data.mappings.reason ?? N}</p>
      <p>历史只用于 MODEL_WARMUP / TRAINING_INPUT / ENGINEERING_VALIDATION，不能展示为历史账户业绩。</p></Box>:null}
  </>;
}

export function EtfQuantPage({section}:{section:EtfSection}) {
  const port=getEtfQuantPort();
  const resource=useResource(signal=>port.getSnapshot(signal),[port,section]);
  const d=resource.data;
  return <div className="flex flex-col gap-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="space-y-2"><Badge variant="warning">SIMULATION_ONLY</Badge>
      <h2 className="text-2xl font-semibold tracking-tight">{TITLES[section]}</h2><p className="text-sm text-muted-foreground">独立 ETF 产品 · 当前最新快照，不是 tick 实时行情；没有真实订单路径。</p></div>
      <Button variant="outline" onClick={resource.retry}>Manual Refresh</Button></div>
    {resource.loading?<LoadingState label="正在读取 ETF Quant 独立快照"/>:resource.error?<Box title="ETF Quant 接口未连接 / 完整性阻断">
      <p>没有自动 mock fallback。请检查独立 API、runtime 配置和完整性门控后手动刷新。</p></Box>:d?<>
      <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm space-y-2">
        <div className="flex flex-wrap gap-x-6 gap-y-1"><strong>{d.status.phase}</strong><span>cutoff：{d.status.cutoff ?? N}</span><span>last update：{d.status.updated_at ?? N}</span>
          <span>signal：{d.status.signal_date ?? N}</span><span>T+1 execution：{d.status.execution_date ?? N}</span></div>
        <p>epoch：{d.status.epoch?.epoch_id ?? 'NOT_STARTED'} · start：{d.status.epoch?.started_at ?? N} · data version：{d.status.source_version ?? N}</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1"><span>provider snapshot <HashText value={d.status.snapshot_id}/></span><span>source commit <HashText value={d.status.source_commit}/></span>
          <span>code commit <HashText value={d.status.code_commit}/></span><span>mapping hash <HashText value={d.status.mapping_hash}/></span><span>strategy hash <HashText value={d.status.strategy_hash}/></span></div>
        <p>{d.status.reason ?? N} · NOT OFFICIAL SHENWAN INDEX · HISTORICAL_MEMBERSHIP_PIT_UNPROVEN</p>
        {d.health.status==='DEGRADED' || d.health.freshness==='STALE'?<p className="text-warning-foreground">数据健康警告：{d.health.status} / {fmt(d.health.freshness)} · {d.health.blockers.join(' · ')}</p>:null}
      </div><Contents section={section} data={d}/>
    </>:null}
  </div>;
}

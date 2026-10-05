import { useResource } from '@/hooks/useResource';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getEtfQuantPort } from '../data-port';
import type { EtfQuantSnapshot } from '../contracts';

const mappingNames={DIRECT_INDUSTRY_TRACKER:'直接行业跟踪',VERIFIED_INDUSTRY_PROXY:'验证行业代理',NO_RELIABLE_MAPPING:'无可靠映射 · CASH'};

export function V2ShadowSection({v1}:{v1?:EtfQuantSnapshot}) {
  const port=getEtfQuantPort();
  const resource=useResource(signal=>port.getV2Current?port.getV2Current(signal):Promise.reject(new Error('V2 unavailable')),[port]);
  const data=resource.data;
  if(!data)return <Card><CardContent className="py-6">{resource.loading?'正在读取 ETF-Quant V2':'V2 接口未连接或完整性阻断，暂无可展示账本。'}</CardContent></Card>;
  const failed=data.historical_classification==='FAIL';
  const dates=[...new Set([...(v1?.nav.map(r=>r.trade_date)??[]),...data.nav.map(r=>r.date)])].sort().slice(-30);
  return <Card><CardHeader><CardTitle>ETF-Quant V2 · 前向 Shadow</CardTitle></CardHeader><CardContent className="space-y-5">
    <p className={failed?'font-semibold text-destructive':'font-semibold'}>{failed?'Experimental / Final-OOS failed / Forward Shadow evaluation':`Final OOS 方向 STRONG_POSITIVE · ${data.scientific_status}`}</p>
    <p className="text-sm">独立统计信心 LIMITED · 历史成员证据 RECONSTRUCTED · 历史 ETF 执行验证 NOT_ESTABLISHED。冻结模型：α=30、RAW、12 个月、H10/40/120，融合 0.25/0.50/0.25。</p>
    <div className="grid gap-4 text-sm sm:grid-cols-3">
      <p>独立初始预算<br/><strong>CNY 10,000</strong></p>
      <p>当前余额<br/><strong>CNY {Number(data.balance).toLocaleString('zh-CN',{maximumFractionDigits:2})}</strong></p>
      <p>现金<br/><strong>{(data.cash_weight*100).toFixed(2)}%</strong></p>
      <p>当前信号日<br/><strong>{data.signal_date??'尚未产生正式信号'}</strong></p>
      <p>Epoch / signal / intent / fill<br/><strong>{data.epoch_count} / {data.signal_count} / {data.intent_count} / {data.fill_count}</strong></p>
      <p>最新事实数据<br/><strong>{data.latest_data_date??'未提供'}</strong><br/>{data.latest_data_time??''}</p>
    </div>
    <p className="text-sm">{data.started?'正式 Shadow 已启动':data.armed?'已布防，等待真实收盘信号':'尚未布防'} · {data.next_accounting_state}。{data.next_eligible_signal_date?`最早候选信号日：${data.next_eligible_signal_date}。`:''}{data.execution_date?`下一记账日期：${data.execution_date}。`:''}</p>
    <p className="text-sm">冻结映射覆盖 {data.mapping_summary.executable_industry_coverage} / 124：直接 {data.mapping_summary.direct_industries}，代理 {data.mapping_summary.proxy_industries}，未映射 {data.mapping_summary.unmapped_industries}。代理门槛 {data.mapping_summary.chosen_proxy_threshold}%；流动性测量日 {data.mapping_summary.latest_liquidity_date}。每次信号重新检查可执行性。</p>
    {data.top5.length?<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Top5 行业</th><th>可执行 ETF</th><th>分配</th><th>映射 / 信心</th><th>证据日期</th></tr></thead><tbody>{data.top5.map(([code,score])=>{const slot=data.slots.find(r=>r.l2_code===code);return <tr key={code}><td className="py-2">{slot?.l2_name??code}<br/><span className="text-xs text-muted-foreground">{score.toFixed(4)}</span></td><td>{slot?.etf_code??'CASH'}</td><td>{((slot?.weight??0)*100).toFixed(2)}%</td><td>{slot?mappingNames[slot.mapping_class]:'无可靠映射'}<br/><span className="text-xs">{slot?.confidence??'—'}</span></td><td>{slot?.evidence_date??'—'}</td></tr>;})}</tbody></table></div>:<p className="text-sm text-muted-foreground">正式信号产生后展示 Top5 和 ETF 分配。</p>}
    <div className="grid gap-4 text-sm sm:grid-cols-3"><p>前向 NAV<br/>{data.nav.length?data.nav.at(-1)?.normalized_nav.toFixed(6):'尚无记账观察'}</p><p>CSI 300<br/>{data.benchmark.points.length?data.benchmark.points.at(-1)?.normalized_nav.toFixed(6):'尚无同日比较'}</p><p>累计成交额 / 初始资金<br/>{data.turnover===null?'暂无成交观察':data.turnover.toFixed(4)}</p></div>
    <div className="space-y-2 text-sm"><h3 className="font-semibold">V1 / V2 并行前向比较</h3><p>两版独立初始资金均为 CNY 10,000，各自从正式 epoch 起点归一化。缺少同日观察显示 —；未启动时不生成 NAV。</p>
      <p>V1：{v1?.status.epoch?'已启动':v1?'尚未启动':'接口未连接'}；V2：{data.started?'已启动':'尚未启动'}。</p>
      {dates.length?<div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th>记账日期</th><th>V1 NAV</th><th>V2 NAV</th><th>V1 CSI 300</th><th>V2 CSI 300</th></tr></thead><tbody>{dates.map(day=><tr key={day}><td>{day}</td><td>{v1?.nav.find(r=>r.trade_date===day)?.normalized_nav??'—'}</td><td>{data.nav.find(r=>r.date===day)?.normalized_nav.toFixed(6)??'—'}</td><td>{v1?.benchmark.points.find(r=>r.trade_date===day)?.normalized.toFixed(6)??'—'}</td><td>{data.benchmark.points.find(r=>r.date===day)?.normalized_nav.toFixed(6)??'—'}</td></tr>)}</tbody></table></div>:<p>尚无前向比较观察。</p>}
    </div>
    <p className="text-xs text-muted-foreground">模拟假设：佣金 3bp、每边滑点 5bp，无印花税和最低佣金；100 份交易单位。真实 T+1 开盘价，完成收盘证据后延迟记账。V1/V2 账本独立。</p>
  </CardContent></Card>;
}

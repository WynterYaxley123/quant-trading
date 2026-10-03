import { useResource } from '@/hooks/useResource';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getEtfQuantPort } from '../data-port';

export function V2ResearchSection() {
  const port=getEtfQuantPort();
  const resource=useResource(signal=>port.getV2Research?port.getV2Research(signal):Promise.reject(new Error('V2 unavailable')),[port]);
  const data=resource.data;
  return <Card><CardHeader><CardTitle>ETF-Quant V2 · 独立研究候选</CardTitle></CardHeader>
    <CardContent className="space-y-3 text-sm">
      {data?<>
        <p>原候选 Validation 未通过；当前修订受该诊断启发，尚未独立验证。Final OOS 保持封存。</p>
        <p>Ridge α={data.specification.alpha} · {data.specification.training_months} 个月 · 原始特征 · H{data.specification.horizons.join(' / H')}。</p>
        <p>事实历史 {data.historical_start} 至 {data.historical_end}，{data.trading_sessions.toLocaleString()} 个交易日；Tier A/B/C：{data.membership_tier_rows.A.toLocaleString()} / {data.membership_tier_rows.B.toLocaleString()} / {data.membership_tier_rows.C.toLocaleString()} 行。Tier D 不用于建模。</p>
        <p>修订 Development RankIC {data.development.mean_rank_ic.toFixed(4)}；原候选 Validation RankIC {data.validation.mean_rank_ic.toFixed(4)}，价差 {data.validation.mean_spread.toFixed(5)}。</p>
        <p>Shadow 工程已准备，尚未启动；epoch / signal / intent / fill 均为 0。未来启动需要人工授权并确认未验证研究状态。</p>
        <p className="break-all text-xs text-muted-foreground">候选 SHA256：{data.candidate_sha256}</p>
      </>:<p>{resource.loading?'正在读取 V2 研究证据':'V2 研究接口未连接或完整性阻断；当前没有可展示的结果。'}</p>}
    </CardContent></Card>;
}

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
        <p>{data.final_oos?data.final_oos.decision.classification==='FAIL'?'Final OOS failed · Experimental forward Shadow。原候选 Validation 未通过；参数保持冻结。':'Final OOS 方向：STRONG_POSITIVE。科学状态：PROVISIONAL_HISTORICAL_RESEARCH_CANDIDATE。原候选 Validation 未通过；修订受 Validation 信息影响，参数保持冻结。':'原候选 Validation 未通过；当前修订尚未独立验证，Final OOS 保持封存。'}</p>
        {data.final_oos && <p>独立统计信心 LIMITED；历史成员证据 RECONSTRUCTED（Tier A 为 0）；历史 ETF 执行验证 NOT_ESTABLISHED。60 个重叠信号日的依赖置信区间和有效样本量均不可估计。行业预测证据不等于可交易 ETF 历史回测。</p>}
        <p>Ridge α={data.specification.alpha} · {data.specification.training_months} 个月 · 原始特征 · H{data.specification.horizons.join(' / H')}。</p>
        <p>事实历史 {data.historical_start} 至 {data.historical_end}，{data.trading_sessions.toLocaleString()} 个交易日；Tier A/B/C：{data.membership_tier_rows.A.toLocaleString()} / {data.membership_tier_rows.B.toLocaleString()} / {data.membership_tier_rows.C.toLocaleString()} 行。Tier D 不用于建模。</p>
        <p>修订 Development RankIC {data.development.mean_rank_ic.toFixed(4)}；原候选 Validation RankIC {data.validation.mean_rank_ic.toFixed(4)}，价差 {data.validation.mean_spread.toFixed(5)}。</p>
        <p>{data.final_oos?`最终检验 RankIC ${data.final_oos.metrics.mean_rank_ic.toFixed(4)}，行业价差 ${data.final_oos.metrics.mean_spread.toFixed(5)}；${data.final_oos.metrics.signals} 个重叠标签信号日。前向 Shadow 状态见版本视图。`:'Shadow 工程已准备，尚未启动；epoch / signal / intent / fill 均为 0。'}</p>
        <p className="break-all text-xs text-muted-foreground">候选 SHA256：{data.candidate_sha256}</p>
      </>:<p>{resource.loading?'正在读取 V2 研究证据':'V2 研究接口未连接或完整性阻断；当前没有可展示的结果。'}</p>}
    </CardContent></Card>;
}

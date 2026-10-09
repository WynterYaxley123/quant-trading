import { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Clock3, FileCheck2, History, Layers3, RefreshCw } from 'lucide-react';
import { fetchRev10Overview, fetchRev10Ranking, rev10Url, type Rev10Overview, type Rev10Ranking } from './rev10-client';

const number=(v:number|null,digits=6)=>v===null?'未定义':`${v>=0?'+':''}${v.toFixed(digits)}`;
const percent=(v:number|null,digits=2)=>v===null?'未定义':`${(v*100).toFixed(digits)}%`;
const names={S0:'等权 / 零评分',S1:'REV5',S2:'REV10',S3:'等权双反转',S4:'固定双因子 Ridge'};
const evidenceNames:Record<string,string>={design:'固定研究设计','chinese-report':'中文研究报告',acceptance:'工程验收','data-boundary':'数据边界','research-decision':'研究决策','source-qualification':'来源资格审计','preregistration-draft':'正式研究草案'};

export function Rev10Page() {
  const [overview,setOverview]=useState<Rev10Overview|null>(null);
  const [ranking,setRanking]=useState<Rev10Ranking|null>(null);
  const [error,setError]=useState('');
  const [rankError,setRankError]=useState('');
  const [revision,setRevision]=useState(0);
  const [scope,setScope]=useState<'top5'|'bottom5'|'rows'>('top5');
  const [chart,setChart]=useState('temporal-blocks');
  const [chartError,setChartError]=useState(false);
  useEffect(()=>{const prior=document.title;document.title='REV10 · 中文研究控制台 | Quant Trading';return ()=>{document.title=prior;};},[]);
  useEffect(()=>{
    const controller=new AbortController();
    Promise.allSettled([fetchRev10Overview(controller.signal),fetchRev10Ranking(controller.signal)]).then(([info,result])=>{
      if(controller.signal.aborted)return;
      if(info.status==='fulfilled')setOverview(info.value);else setError('研究接口无法连接或报告完整性校验失败。未展示替代指标。');
      if(result.status==='fulfilled')setRanking(result.value);else setRankError('排名完整性校验失败或接口不可用，未展示任何行业数值。');
    });
    return ()=>controller.abort();
  },[revision]);
  const retry=()=>{setOverview(null);setRanking(null);setError('');setRankError('');setRevision(v=>v+1);};
  if(error)return <section role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-8 text-slate-800"><h1 className="text-xl font-semibold">REV10 研究成果暂不可用</h1><p className="my-3">{error}</p><button onClick={retry} className="rounded border px-4 py-2">重新连接</button><a href="/offline-review/index.html" className="ml-4 underline">打开本地离线成果包</a></section>;
  if(!overview)return <p role="status" className="rounded-xl border p-8">正在核验 REV10 研究报告与历史排名…</p>;
  const h10=overview.models.S2['10'],h5=overview.models.S2['5'];
  const rows=ranking?.status==='HISTORICAL_REPLAY'?ranking[scope]:[];
  const asof=ranking?.status==='HISTORICAL_REPLAY'?ranking.asof:overview.historical_cutoff;
  const states=[
    ['模型实现','研究专用 · 已完成',true],['历史探索','已完成',true],['预注册草案','已准备',true],
    ['统计设计','待完成',false],['正式预注册','未激活',false],['真实来源准入','0 · 未就绪',false],
    ['生产签名身份','未建立',false],['真实前瞻观测','0',false],['独立 Validation','未开始',false],
  ] as const;
  return <div className="space-y-6 text-slate-800">
    <section className="relative overflow-hidden rounded-xl bg-[#142c40] p-6 text-white md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs tracking-[0.18em] text-slate-300">SWL1 / SHORT HORIZON RESEARCH</p><span className="rounded bg-amber-100 px-3 py-1 text-xs font-medium text-amber-900">EXPLORATORY_POST_HOC · 后验探索</span></div>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">REV10 · 短周期行业研究</h1>
      <p className="mt-3 text-sm leading-6 text-slate-200">SWL1 REV10 Short-V1 · 固定规则，无需训练 · 30 个申万一级行业<br/>主终点 H10 / 次终点 H5 · CNEquity 重建等权相对收益</p>
      <div className="mt-5 flex flex-wrap gap-5 text-xs text-slate-300"><span className="flex items-center gap-2"><History size={15}/>历史数据截止 {overview.historical_cutoff}</span><span className="flex items-center gap-2"><Layers3 size={15}/>已冻结定义 · 未经独立验证</span><button onClick={retry} className="ml-auto flex items-center gap-2 text-white"><RefreshCw size={14}/>重新核验</button></div>
    </section>
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {[[`H10 平均 RankIC`,number(h10.rank_ic.mean),`${h10.signal_count} 个历史截面 · 主要周期`],[`H5 平均 RankIC`,number(h5.rank_ic.mean),`${h5.signal_count} 个历史截面 · 次要周期`],[`H10 RankIC 正向比例`,percent(h10.rank_ic.positive_fraction),'重叠样本，非独立试验'],[`H5 RankIC 正向比例`,percent(h5.rank_ic.positive_fraction),'直接读取 PR36 已核验报告']].map(([label,value,note])=><section key={label} className="rounded-xl border border-slate-200 bg-white p-4 md:p-5"><p className="text-xs text-slate-500">{label}</p><p className="my-3 text-2xl font-semibold tabular-nums text-teal-700 md:text-3xl">{value}</p><p className="text-xs leading-5 text-slate-500">{note}</p></section>)}
    </div>
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
      <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">30 行业研究排名</h2><p className="mt-1 text-xs text-slate-500">历史研究排名 · 不代表今日行情 · 截至 {asof}</p></div><span className="rounded bg-slate-100 px-2 py-1 text-xs">HISTORICAL_REPLAY</span></div>
        {ranking?.status==='HISTORICAL_REPLAY'?<>
          <div role="group" aria-label="排名范围" className="my-5 flex flex-wrap gap-2">{([['top5','Top5'],['bottom5','Bottom5'],['rows','全部 30 行业']] as const).map(([key,label])=><button key={key} aria-pressed={scope===key} onClick={()=>setScope(key)} className={`rounded-md border px-4 py-2 text-sm ${scope===key?'border-[#142c40] bg-[#142c40] text-white':'border-slate-200 bg-white text-slate-600'}`}>{label}</button>)}<span className="ml-auto self-center text-xs text-teal-700">30 / 30 完整</span></div>
          <div className="overflow-x-auto"><table aria-label="REV10 历史行业排名" className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['排名','行业 / 代码','REV10 原始评分','相对评分','10 日平均收益','完整性'].map(s=><th key={s} className="whitespace-nowrap px-3 py-3 font-medium">{s}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.industry_code} className="border-b border-slate-100"><td className="px-3 py-4 font-mono text-slate-400">{String(row.rank).padStart(2,'0')}</td><td className="whitespace-nowrap px-3 py-4 font-medium">{row.industry_name}<span className="mt-1 block font-mono text-xs font-normal text-slate-400">{row.industry_code}{!row.name_verified?' · 名称未核实':''}</span></td><td className="px-3 py-4 text-right font-mono">{number(row.rev10_score*100,4)}%</td><td className={`px-3 py-4 text-right font-mono ${row.relative_score>=0?'text-teal-700':'text-amber-700'}`}>{number(row.relative_score*100,4)}%</td><td className="px-3 py-4 text-right font-mono text-slate-500">{number(row.trailing_mean_return*100,4)}%</td><td className="whitespace-nowrap px-3 py-4 text-xs text-slate-500">10/10 完整</td></tr>)}</tbody></table></div>
          <p className="mt-4 text-xs leading-5 text-slate-500">评分及日均收益以百分比展示。按 REV10 原始评分降序、行业代码升序处理并列；中心化不改变排名。Bottom5 按评分升序展示。</p>
          <details className="mt-3 text-xs text-slate-500"><summary className="cursor-pointer">查看数据时间与校验信息</summary><div className="mt-2 space-y-2 break-all"><p>窗口：{ranking.window_sessions[0]} → {ranking.window_sessions.at(-1)} · 数据截至 {ranking.asof}</p><p>来源 generation：{ranking.source_generation}</p><p>工件 hash：{ranking.manifest_sha256}</p><p>RESEARCH_REPLAY_ONLY · 原始访问隔离 NOT_CERTIFIED</p></div></details>
        </>:<p role="alert" className="mt-5 rounded-lg bg-amber-50 p-4 text-sm text-amber-900">{rankError||'排名不可用：本机未配置经过核验的私有历史重放工件。'} 历史聚合指标仍可查看。</p>}
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="flex items-center gap-2 text-lg font-semibold"><FileCheck2 size={19}/>规则与实验状态</h2><p className="my-4 text-sm leading-6 text-slate-600">REV10 = 过去 10 个每日收益的负<strong>算术均值</strong>，含信号日 T 收盘。横截面中心化后用于相对排名。</p>{states.map(([label,state,ready])=><div key={label} className="flex items-center justify-between gap-2 border-t border-slate-100 py-3 text-xs"><span className="text-slate-500">{label}</span><span className={`flex items-center gap-1.5 ${ready?'text-teal-700':'text-amber-700'}`}>{ready?<CheckCircle2 size={13}/>:<Clock3 size={13}/>} {state}</span></div>)}<p className="mt-4 text-xs leading-5 text-slate-500">数据状态：DATA_SOURCE_NOT_READY<br/>V1 / V2：FAILED_VALIDATION<br/>Final OOS：未开启<br/>历史独立未见 session：0</p></section>
    </div>
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="mb-4 text-lg font-semibold">历史基线比较</h2><div className="overflow-x-auto"><table aria-label="历史基线比较" className="w-full text-sm"><thead className="text-left text-xs text-slate-500"><tr><th className="pb-3">固定规格</th><th>H5 平均 RankIC</th><th>H10 平均 RankIC</th></tr></thead><tbody>{(['S0','S1','S2','S3','S4'] as const).map(id=><tr key={id} className={`border-t border-slate-100 ${id==='S2'?'bg-teal-50 font-medium text-teal-800':''}`}><td className="py-3">{names[id]}</td><td className="font-mono">{number(overview.models[id]['5'].rank_ic.mean)}</td><td className="font-mono">{number(overview.models[id]['10'].rank_ic.mean)}</td></tr>)}</tbody></table></div><p className="mt-3 text-xs leading-5 text-slate-500">本次固定规格 Ridge 未增加有效信息。零横截面评分的 RankIC 未定义；原始收益差不代表可执行净利润。</p></section>
      <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="mb-4 text-lg font-semibold">REV10 · 四个固定时间块</h2><table aria-label="四个时间块" className="w-full text-sm"><thead className="text-left text-xs text-slate-500"><tr><th className="pb-3">时间块</th><th>H5 RankIC</th><th>H10 RankIC</th></tr></thead><tbody>{h10.calendar_blocks.map((block,i)=><tr key={block.block} className="border-t border-slate-100"><td className="py-3">时间块 {block.block}</td><td className="font-mono">{number(h5.calendar_blocks[i]?.rank_ic.mean ?? null)}</td><td className="font-mono">{number(block.rank_ic.mean)}</td></tr>)}</tbody></table><p className="mt-3 text-xs leading-5 text-slate-500">后期 H5 明显减弱。全样本正值不能解释为持续稳定的预测能力。</p></section>
    </div>
    <section className="rounded-xl border border-slate-200 bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">研究图表</h2><span className="text-xs text-slate-500">复用 PR36 原始六张图 · 未重新计算历史结果</span></div><div className="my-4 flex flex-wrap gap-2">{overview.charts.map(item=><button key={item.id} aria-pressed={chart===item.id} onClick={()=>{setChart(item.id);setChartError(false);}} className={`rounded border px-3 py-2 text-xs ${chart===item.id?'border-teal-700 bg-teal-50 text-teal-800':'border-slate-200'}`}>{item.title}</button>)}</div>{chartError?<p role="alert">图表不可用或完整性校验失败。</p>:<div className="overflow-hidden rounded-lg border bg-white"><img src={rev10Url(`chart/${chart}`)} alt={overview.charts.find(item=>item.id===chart)?.title} className="h-auto w-full" onError={()=>setChartError(true)}/></div>}</section>
    <div className="grid gap-6 lg:grid-cols-2"><section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold">稳定性与研究局限</h2><ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600"><li>逐一排除 30 个行业仍保留正向全样本均值；共同因素和联合偏差未排除。</li><li>标签重叠，行业相关；描述性块分析不能替代独立验证。</li><li>当前分类重建未认证历史 PIT，生存偏差及复权约定仍有局限。</li><li>原始价差不是净利润，机制尚未识别。</li><li>本次历史访问授权不等于供应商许可证或生产准入。</li></ul></section><section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold">研究证据</h2><div className="mt-4 grid gap-2 sm:grid-cols-2">{overview.evidence.map(item=><a key={item.id} href={rev10Url(`evidence/${item.id}`)} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-xs hover:bg-slate-50">{evidenceNames[item.id]}<ArrowRight size={13}/></a>)}<a href={overview.research_pr} target="_blank" rel="noreferrer" className="rounded-lg border p-3 text-xs">PR #36 · 已有历史研究</a><a href="/offline-review/index.html" className="rounded-lg border p-3 text-xs">本地离线成果包</a></div><details className="mt-4 text-xs text-slate-500"><summary className="cursor-pointer">核验事实来源</summary><p className="mt-2 break-all leading-5">报告 hash：{overview.source_hashes.summary}<br/>模型 hash：{overview.model_hash}</p></details></section></div>
  </div>;
}

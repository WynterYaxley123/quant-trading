import { useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useResource } from '@/hooks/useResource';
import { fetchFamilies, fetchForecast, fetchComparison } from './client';

const number=(value:number|null|undefined)=>value==null?'—':value.toFixed(4);
const percent=(value:number|null|undefined)=>value==null?'—':`${(value*100).toFixed(2)}%`;
const horizons=[10,40,120];

export function IndustryForecastPage() {
  const [family,setFamily]=useState('swl2_ridge_v1');
  const [date,setDate]=useState('');
  const [horizon,setHorizon]=useState(10);
  const families=useResource(fetchFamilies,[]);
  const forecast=useResource(signal=>fetchForecast(family,signal),[family]);
  const comparison=useResource(fetchComparison,[]);
  const view=forecast.data;
  const definition=view?.family??families.data?.find(f=>f.family_id===family);
  const selected=view?.history.find(f=>f.signal_date===date)??view?.current;
  const evaluated=view?.evaluations.find(e=>e.signal_date===selected?.signal_date&&e.horizon===horizon);
  const names=new Map(selected?.cross_section.map(r=>[r.industry_code,r.industry_name])??[]);
  const pending=(h:number)=>view?.evaluations.find(e=>e.signal_date===selected?.signal_date&&e.horizon===h);
  return <div className="flex flex-col gap-6">
    <section className="rounded-xl border bg-card p-5">
      <h1 className="text-2xl font-semibold">Industry Forecast</h1>
      <p className="mt-2 text-sm text-muted-foreground">申万二级行业预测研究 · NON_TRADABLE_RESEARCH_DIAGNOSTIC</p>
      <p className="mt-2 text-sm">科学目标：exact h-session 行业复合收益减去该家族完整冻结宇宙在同一 (t,h) 的均值。走势图仅为 VISUAL_TREND_DIAGNOSTIC。</p>
      <label className="mt-4 flex items-center gap-3">策略家族
        <select aria-label="策略家族" className="rounded border bg-background p-2" value={family} onChange={e=>{setFamily(e.target.value);setDate('');}}>
          {families.data?.map(f=><option key={f.family_id} value={f.family_id}>{f.display_name}</option>)}
          {!families.data?<><option value="swl2_ridge_v1">SWL2-Ridge-V1</option><option value="swl2_ridge_v2">SWL2-Ridge-V2</option></>:null}
        </select>
      </label>
      <p className="mt-3 text-sm">{view?.family.scientific_status??'正在读取研究状态'} · INDUSTRY_FORECAST_RESEARCH · ETF_PRODUCTIZATION_RETIRED</p>
      {definition?<p className="mt-2 text-sm">Taxonomy ({definition.taxonomy_scope}): {definition.taxonomy_universe_size} · Frozen model universe: {definition.model_universe_size} · Published forecast rows: {view?.current?.forecast_row_count??0} · {definition.taxonomy_only_industries.length} taxonomy-only industries: NOT_IN_FROZEN_MODEL_UNIVERSE</p>:null}
      {view?.family.generation===2?<p className="mt-2 text-sm">历史 directional Final OOS: STRONG_POSITIVE · independent confidence: LIMITED · membership: RECONSTRUCTED · historical ETF execution: NOT_ESTABLISHED</p>:<p className="mt-2 text-sm">SWL2-Ridge-V1 frozen baseline · Validation / Final OOS 保持 SEALED</p>}
      {families.error||forecast.error?<p role="alert">Industry Forecast API unavailable or integrity blocked. 无法读取前瞻证据。</p>:null}
      {forecast.loading?<p>正在读取前瞻预测…</p>:null}
      {!forecast.loading&&!forecast.error&&!selected?<p className="mt-4">No forward forecasts yet. 不回填历史研究结果。</p>:null}
    </section>

    {selected?<><section className="rounded-xl border bg-card p-5">
      <h2 className="text-lg font-semibold">Current Forecast / Signal history</h2>
      <label className="my-3 flex gap-3">Signal date<select aria-label="Signal date" className="rounded border bg-background p-1" value={selected.signal_date} onChange={e=>setDate(e.target.value)}>{view?.history.map(f=><option key={f.signal_date}>{f.signal_date}</option>)}</select></label>
      <p>Data cutoff {selected.data_cutoff} · Published {selected.published_at}</p>
      <p className="mt-2 text-sm">RECONSTRUCTED_SWL2_EQUAL_WEIGHT · {selected.provenance.data_source} · available-at {selected.provenance.available_at}</p>
      <p className="mt-1 break-all text-xs">Snapshot SHA256 {selected.provenance.snapshot_sha256} · Source commit {selected.source_commit}</p>
      <h3 className="mt-4 font-semibold">Top5 predicted industries · fused ranking</h3>
      <ol className="mt-2 grid gap-2 sm:grid-cols-5">{selected.cross_section.slice(0,5).map(r=><li key={r.industry_code} className="rounded border p-3">#{r.fused_rank} {r.industry_name}<p className="text-sm text-muted-foreground">{r.industry_code} · {number(r.fused_score)}</p></li>)}</ol>
    </section><section className="overflow-x-auto rounded-xl border bg-card p-5">
      <h2 className="mb-3 text-lg font-semibold">Full Ranking · {selected.industry_count} industries</h2>
      <table className="w-full text-sm"><thead><tr>{['Rank','Industry','Fused score',...horizons.map(h=>`H${h} raw / z / rank`)].map(label=><th key={label} className="p-2 text-left">{label}</th>)}</tr></thead>
        <tbody>{selected.cross_section.map(r=><tr key={r.industry_code} className="border-t"><td className="p-2">{r.fused_rank}</td><td>{r.industry_name} · {r.industry_code}</td><td>{number(r.fused_score)}</td>{horizons.map(h=>{const c=r.horizons[String(h) as '10'|'40'|'120'];return <td key={h}>{number(c.raw_prediction)} / {number(c.cross_section_zscore)} / #{c.rank}</td>;})}</tr>)}</tbody></table>
    </section></>:null}

    <section className="overflow-x-auto rounded-xl border bg-card p-5">
      <h2 className="text-lg font-semibold">Forecast Evaluation · SCIENTIFIC_TARGET</h2>
      <p className="my-2 text-sm">RECONSTRUCTED_SWL2_EQUAL_WEIGHT。H10/H40/H120 为真实交易 session；未成熟或未 finalized 均为 PENDING。</p>
      {!view?.metrics.some(m=>m.matured_forecast_dates>0)?<p>No matured forward observations yet.</p>:null}
      <table className="mt-3 w-full text-sm"><thead><tr>{['Horizon','Matured dates','Mean RankIC','Median RankIC','Positive fraction','Top5 return','Bottom5 return','Spread','SWL2 universe EW'].map(s=><th key={s} className="p-2 text-left">{s}</th>)}</tr></thead><tbody>{view?.metrics.map(m=><tr key={m.horizon} className="border-t"><td className="p-2">H{m.horizon}</td><td>{m.matured_forecast_dates}</td><td>{number(m.mean_rank_ic)}</td><td>{number(m.median_rank_ic)}</td><td>{percent(m.positive_rank_ic_fraction)}</td><td>{percent(m.top5_mean_return)}</td><td>{percent(m.bottom5_mean_return)}</td><td>{percent(m.top5_bottom5_spread)}</td><td>{percent(m.universe_mean_return)}</td></tr>)}</tbody></table>
      {view?.metrics.map(m=><p key={m.horizon} className="mt-2 text-xs">H{m.horizon}: {m.confidence_status} · worst rolling 20-date spread interval {m.worst_rolling_interval?`${m.worst_rolling_interval.from} → ${m.worst_rolling_interval.through}: ${percent(m.worst_rolling_interval.spread)}`:'PENDING'}</p>)}
    </section>

    {selected?<section className="overflow-x-auto rounded-xl border bg-card p-5">
      <h2 className="text-lg font-semibold">Predicted vs Realized · {selected.signal_date}</h2>
      <label className="my-3 flex gap-3">Horizon<select aria-label="Horizon" className="rounded border bg-background p-1" value={horizon} onChange={e=>setHorizon(Number(e.target.value))}>{horizons.map(h=><option key={h} value={h}>H{h}</option>)}</select></label>
      <p>{horizons.map(h=>`H${h}: ${pending(h)?'MATURED':'PENDING'}`).join(' · ')}</p>
      {evaluated?<><p className="mt-2">Predicted Top5: {evaluated.metrics.predicted_top5.map(c=>names.get(c)??c).join(' / ')}</p><p>Actual future Top5: {evaluated.metrics.actual_top5.map(c=>names.get(c)??c).join(' / ')}</p><p>Overlap {evaluated.metrics.top5_overlap_count}/5 · {percent(evaluated.metrics.top5_overlap_rate)} · Mean / median absolute rank error {number(evaluated.metrics.mean_absolute_rank_error)} / {number(evaluated.metrics.median_absolute_rank_error)}</p><p>Fused Top5 horizon outcome {percent(evaluated.metrics.fused_top5_mean_return)} · NON_TRADABLE_RESEARCH_DIAGNOSTIC</p></>:null}
      <table className="mt-3 w-full text-sm"><thead><tr><th>Industry</th><th>Fused rank / score</th>{horizons.map(h=><th key={h}>H{h} predicted raw / rank → scientific target / raw realized return / rank</th>)}</tr></thead><tbody>{selected.cross_section.map(r=><tr key={r.industry_code} className="border-t"><td className="p-2">{r.industry_name} · {r.industry_code}</td><td>#{r.fused_rank} / {number(r.fused_score)}</td>{horizons.map(h=>{const outcome=pending(h)?.metrics.realized.find(e=>e.industry_code===r.industry_code);const component=r.horizons[String(h) as '10'|'40'|'120'];return <td key={h}>{number(component.raw_prediction)} / #{component.rank} → {outcome?`${percent(outcome.scientific_target)} / ${percent(outcome.realized_return)} / #${outcome.realized_rank}`:'PENDING'}</td>;})}</tr>)}</tbody></table>
      <p className="mt-2 text-xs">scientific_target != raw_realized_return；center 使用该家族完整冻结模型宇宙。</p>
      {evaluated?<><h3 className="mt-5 font-semibold">Trend View · normalized start 1.0</h3><p className="my-2 text-sm">VISUAL_TREND_DIAGNOSTIC · NORMALIZED_RESEARCH_INDEX · NON_TRADABLE_RESEARCH_DIAGNOSTIC · RECONSTRUCTED_SWL2_EQUAL_WEIGHT</p><div className="h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={evaluated.visual_trend_diagnostic.points.map(p=>({date:p.date,universe_equal_weight:p.universe_equal_weight,...p.values}))}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="date"/><YAxis domain={['auto','auto']}/><Tooltip/><Line dataKey="universe_equal_weight" name="SWL2 universe equal-weight" stroke="#64748b" dot={false}/>{evaluated.metrics.predicted_top5.map((code,i)=><Line key={code} dataKey={code} name={names.get(code)??code} stroke={['#2563eb','#059669','#d97706','#7c3aed','#db2777'][i]} dot={false}/>)}</LineChart></ResponsiveContainer></div></>:<p className="mt-3">PENDING · 不读取或显示 provisional future values。</p>}
    </section>:null}

    <section className="overflow-x-auto rounded-xl border bg-card p-5">
      <h2 className="text-lg font-semibold">SWL2-Ridge-V1 vs SWL2-Ridge-V2 · COMMON_FORWARD_WINDOW</h2>
      <p className="my-2 text-sm">COMMON_INDUSTRY_CROSS_SECTION_DIAGNOSTIC：仅比较共同日期、成熟 horizon 和共有行业的相同 realized return。V1 冻结宇宙 {families.data?.[0]?.model_universe_size??'—'}、V2 冻结宇宙 {families.data?.[1]?.model_universe_size??'—'}；PRIMARY FAMILY METRICS 保持原宇宙。Centered target 不要求跨家族相等。历史 sealed / consumed OOS 不进入比较。</p>
      {comparison.error?<p role="alert">Common forward comparison unavailable or target provenance mismatch.</p>:null}
      <table className="mt-3 w-full text-sm"><thead><tr><th>Horizon</th><th>Common dates / industries</th><th>SWL2-Ridge-V1 mean / median / positive / spread</th><th>SWL2-Ridge-V2 mean / median / positive / spread</th><th>Difference SWL2-Ridge-V2 − SWL2-Ridge-V1</th></tr></thead><tbody>{comparison.data?.map(c=><tr key={c.horizon} className="border-t"><td className="p-2">H{c.horizon}</td><td>{c.matured_common_date_count} / {[...new Set(Object.values(c.common_industry_counts))].join(", ")||"—"}</td>{[c.swl2_ridge_v1,c.swl2_ridge_v2,c.difference_v2_minus_v1].map((m,i)=><td key={i}>{number(m.mean_rank_ic)} / {number(m.median_rank_ic)} / {percent(m.positive_rank_ic_fraction)} / {percent(m.top5_bottom5_spread)}</td>)}</tr>)}</tbody></table>
      {comparison.data?.map(c=><p key={c.horizon} className="mt-2 text-xs">H{c.horizon} common diagnostic: {c.raw_return_compatibility} · V1/V2 mean rank error {number(c.swl2_ridge_v1.mean_absolute_rank_error)} / {number(c.swl2_ridge_v2.mean_absolute_rank_error)} · Top5 overlap {percent(c.swl2_ridge_v1.top5_overlap_rate)} / {percent(c.swl2_ridge_v2.top5_overlap_rate)}</p>)}
      <p className="mt-3 text-xs">Descriptive evidence only · overlapping horizons · 不提供显著性胜负声明。</p>
    </section>
  </div>;
}

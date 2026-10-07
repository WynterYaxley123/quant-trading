import type { Family } from './contracts';

const number=(value:number|null|undefined)=>value==null?'—':value.toFixed(6);

export function ResearchEvidence({family}:{family:Family}) {
  const evidence=family.research_evidence;
  if(!evidence)return null;
  const validation=evidence.validation;
  return <section className="overflow-x-auto rounded-xl border bg-card p-5">
    <h2 className="text-lg font-semibold">{family.display_name} · Historical research lifecycle</h2>
    <p className="my-2 text-sm">{family.primary_series} · NON_TRADABLE_RESEARCH_DIAGNOSTIC · confidence LIMITED · overlapping horizons</p>
    <p>Validation: {family.validation_status} · Final OOS: {family.final_oos_status}</p>
    <p>Candidate: {evidence.selected_spec?`Policy ${evidence.selected_spec.policy} / ${evidence.selected_spec.months} months / penalty ${evidence.selected_spec.penalty} × training rows`:'not_selected'}</p>
    <p className="mt-2 break-all text-xs">Protocol SHA256 {family.protocol_hash} · Candidate SHA256 {family.candidate_hash??'not_applicable'}</p>
    <p className="mt-1 break-all text-xs"><a href={evidence.anchor.github_url}>Public preregistration</a> · commit {evidence.anchor.protocol_commit} · merge {evidence.anchor.merge_sha}</p>
    <h3 className="mt-4 font-semibold">Development · frozen 16-spec budget</h3>
    <p>{evidence.ranges.development?.start} → {evidence.ranges.development?.end}</p>
    {evidence.development?<table className="mt-3 w-full text-sm"><thead><tr>{['Spec','Admitted','Valid / required / dropped','Composite RankIC','H10','H40','H120','Positive blocks'].map(label=><th key={label} className="p-2 text-left">{label}</th>)}</tr></thead><tbody>{evidence.development.leaderboard.map(row=><tr key={row.id} className="border-t"><td className="p-2">{row.id}</td><td>{row.admitted?'YES':'NO'}</td><td>{row.metrics.signal_count} / {row.metrics.required_signal_count} / {row.metrics.dropped_signals.length}</td><td>{number(row.metrics.composite_rank_ic)}</td>{[10,40,120].map(h=><td key={h}>{number(row.metrics.horizons[String(h)]?.mean_rank_ic)}</td>)}<td>{row.metrics.positive_blocks}/4</td></tr>)}</tbody></table>:<p>Development: NOT_OPENED</p>}
    <h3 className="mt-4 font-semibold">Validation · at most one opening</h3>
    {validation?<><p>{evidence.ranges.validation?.start} → {evidence.ranges.validation?.end} · {validation.passed?'PASS':'FAIL'} · valid {validation.metrics.signal_count}/{validation.metrics.required_signal_count} · dropped {validation.metrics.dropped_signals.length}</p><p>Composite RankIC {number(validation.metrics.composite_rank_ic)} · median {number(validation.metrics.median_composite_rank_ic)} · positive fraction {number(validation.metrics.weighted_positive_fraction)} · weighted spread {number(validation.metrics.weighted_spread)}</p><table className="mt-3 w-full text-sm"><thead><tr><th>Horizon</th><th>Mean RankIC</th><th>Median RankIC</th><th>Positive fraction</th><th>Raw spread</th></tr></thead><tbody>{[10,40,120].map(h=>{const m=validation.metrics.horizons[String(h)];return <tr key={h}><td>H{h}</td><td>{number(m?.mean_rank_ic)}</td><td>{number(m?.median_rank_ic)}</td><td>{number(m?.positive_fraction)}</td><td>{number(m?.spread)}</td></tr>;})}</tbody></table><p className="mt-3">Equal-calendar blocks: {validation.metrics.block_composite_rank_ic.map(number).join(' / ')} · signal counts {validation.metrics.block_signal_counts.join(' / ')} · positive {validation.metrics.positive_blocks}/4</p></>:<p>Validation: NOT_OPENED · no metrics exist.</p>}
    <p className="mt-3">{family.scientific_status==='FAILED_VALIDATION'?'V2 permanently closed. No retry or retuning.':family.scientific_status==='AWAITING_PROSPECTIVE_FINAL_OOS'?'Future-only OOS required; no historical backfill.':'No candidate or unopened Validation; forward publication disabled.'}</p>
  </section>;
}

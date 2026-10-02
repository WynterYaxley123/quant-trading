// Synthetic, isolated boundary fixtures only. Never used by production or copied
// to the approved artifact root; all values deliberately lack research meaning.
import { createHash } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { CANDIDATES, HORIZONS, METRIC_NAMES, METRIC_STEMS, PROTOCOL_HASH, SPLIT_HASH, PREDICTION_HASH, SECTOR_SNAPSHOT } from '../src/protocol.js'
import { DAILY_COLUMNS, PREDICTION_COLUMNS, TRAINING_COLUMNS } from '../src/schemas/csv.js'
export const fixtureRun = 'iteration1_20260101_000000_000000_utc'
export const hash = (text: string) => createHash('sha256').update(text).digest('hex')
const aggregate = Object.fromEntries(METRIC_NAMES.map((name) => [name, {
  valid_dates: 0, null_dates: 100, mean: null, median: null, std: null, min: null, max: null,
}]))
const csv = (header: readonly string[], rows: unknown[][]) => header.join(',') + '\n' + rows.map((row) => row.join(',')).join('\n') + '\n'
const daily: unknown[][] = [], predictions: unknown[][] = [], training: unknown[][] = []
for (let ordinal = 1; ordinal <= 100; ordinal++) {
  const date = new Date(Date.UTC(2025, 0, ordinal)).toISOString().slice(0, 10)
  for (const horizon of HORIZONS) {
    for (const stem of METRIC_STEMS) daily.push([ordinal, date, horizon, `${stem}_${horizon}`, '', 'TEST_UNAVAILABLE', 124])
    training.push([ordinal, date, horizon, 'skipped', 'TEST_ONLY', '', '', '', '', '', 0, 0, 0, 124, 0, 0, 0, 0])
    for (let sector = 0; sector < 124; sector++) {
      predictions.push([ordinal, date, String(801000 + sector), 'TEST_ONLY', horizon, '', '', '', '', sector < 5 ? 'True' : 'False', '', '', 'TEST_UNAVAILABLE', 0, 0, ''])
    }
  }
}
const contents: Record<string, string> = {
  'aggregate_metrics.json': JSON.stringify(aggregate),
  'per_date_metrics.csv': csv(DAILY_COLUMNS, daily),
  'predictions.csv': csv(PREDICTION_COLUMNS, predictions),
  'training_diagnostics.csv': csv(TRAINING_COLUMNS, training),
  'per_date_predictions.csv': 'TEST_ONLY_UNUSED_WIDE_EVIDENCE\n',
  'data_quality_diagnostics.json': JSON.stringify({attempted_development_dates:100,successful_dates:0,skipped_dates:[],missing_factor_exclusions:0,missing_label_exclusions:0,numerical_failures:0,insufficient_training_cases:0}),
  'transformation_diagnostics.json': JSON.stringify({zero_std_feature_occurrences:0,scaler_diagnostic_hash:null,target_diagnostic_hash:null,demean_residual_max_abs_mean:null}),
}
const summary = JSON.stringify({
  comparison: CANDIDATES.map((candidate) => ({candidate,Weighted_RankIC:null,Weighted_Spread:null,RankIC_10:null,RankIC_40:null,RankIC_120:null,Spread_10:null,Spread_40:null,Spread_120:null,promotion_status:'NOT PROMOTED'})),
  all_candidate_aggregate_metrics:Object.fromEntries(CANDIDATES.map((id) => [id,aggregate])),
  review_priority:[],promotion_result:'NO_ITERATION1_CANDIDATE_PROMOTED',d0_control_sha256:{},
})
export async function writeRun(root: string, runId = fixtureRun) {
  const runDir = join(root, 'shenwan_sector_index', runId)
  await mkdir(runDir, {recursive:true})
  await writeFile(join(runDir, 'candidate_summary.json'), summary)
  for (const id of CANDIDATES) {
    await mkdir(join(runDir, id))
    for (const [name, text] of Object.entries(contents)) await writeFile(join(runDir, id, name), text)
  }
  const metadata = {
    run_id:runId,research_label:'SECTOR_INDEX_RESEARCH_ONLY',phase:'DEVELOPMENT',iteration:1,
    candidate_family:CANDIDATES,candidate_family_size:4,new_candidate_count:3,
    executable:false,strict_pit:false,classification_admission:'FIXED_CLASSIFICATION_RESEARCH',
    validation_access:'SEALED',final_oos_access:'SEALED',etf_execution:'DISABLED',synthetic_portfolio:'DISABLED',level_b:'DISABLED',
    synthetic_portfolio_config_hash:null,split_policy_hash:SPLIT_HASH,prediction_config_hash:PREDICTION_HASH,
    development_iteration1_protocol_hash:PROTOCOL_HASH,sector_snapshot_id:SECTOR_SNAPSHOT,
    git_head:'0'.repeat(40),environment_changed:false,development_ordinals:[1,100],notices:['NOT TRADABLE','TEST ONLY'],
    content_sha256:{'candidate_summary.json':hash(summary),...Object.fromEntries(CANDIDATES.map((id) => [id,Object.fromEntries(Object.entries(contents).map(([name,text]) => [name,hash(text)]))]))},
  }
  const text = JSON.stringify(metadata)
  await writeFile(join(runDir, 'metadata.json'), text)
  return {runDir,metadata,text}
}
export function approved(runId: string, text: string) {
  const m = runId.match(/^iteration1_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(\d{6})_utc$/)!
  return {runId,createdAt:`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}.${m[7]}Z`,timeSource:'METADATA_RUN_ID_UTC',metadataSha256:hash(text)}
}
export async function writeRegistry(root: string, runs: ReturnType<typeof approved>[]) {
  const registryPath = join(root, 'approval.json')
  await writeFile(registryPath, JSON.stringify({schemaVersion:'1.0.0',workspaces:[{
    artifactId:'test-development',collection:'shenwan_sector_index',phase:'DEVELOPMENT',approvalState:'APPROVED',
    approvalBasis:'OWNER_AUTHORIZED_EXISTING_DEVELOPMENT_ACCEPTANCE',evidence:'TEST_ONLY',runs,
  }]}))
  return registryPath
}

import {afterEach,describe,it,expect,vi} from 'vitest';
import {readFileSync} from 'node:fs';
import {cleanup,render,screen} from '@testing-library/react';
import {EvidenceReadiness} from '@/industry-forecast/EvidenceReadiness';
import {evidenceReadinessSchema,fetchEvidenceReadiness} from '@/industry-forecast/evidence-client';

vi.mock('@/industry-forecast/evidence-client',async importOriginal=>({...await importOriginal<object>(),fetchEvidenceReadiness:vi.fn()}));
const record=JSON.parse(readFileSync('../reports/research/swl1_data_first/prospective-readiness.json','utf8'));
afterEach(()=>{cleanup();vi.clearAllMocks();});
describe('scientific and engineering readiness remain separate',()=>{
  it('shows frozen failures, blocked rights, uncertified history and zero formal evidence',async()=>{
    vi.mocked(fetchEvidenceReadiness).mockResolvedValue(evidenceReadinessSchema.parse(record));render(<EvidenceReadiness/>);
    expect(await screen.findByText(/下一代研究：暂缓/)).toBeInTheDocument();
    expect(screen.getByText(/NOT_CERTIFIED/)).toBeInTheDocument();expect(screen.getByText(/NONE · 观察 0/)).toBeInTheDocument();
    expect(screen.getByText(/V1 \/ V2：Validation 失败/)).toBeInTheDocument();expect(screen.queryByText('READY_TO_TRADE')).not.toBeInTheDocument();
  });
  it('does not infer readiness when the observer fails',async()=>{
    vi.mocked(fetchEvidenceReadiness).mockRejectedValue(new Error('blocked'));render(<EvidenceReadiness/>);
    expect(await screen.findByRole('alert')).toHaveTextContent('无法确认来源准入');
  });
  it('rejects fake live, reopened failure, nonzero evidence and missing platform limits',()=>{
    for(const value of [{...record,live_activation:true},{...record,formal_observations:1},{...record,future_protocol:'V3'},{...record,process_isolation:'PASS_WINDOWS_NATIVE'},{...record,models:{...record.models,swl1_ridge_v2:'PASS'}}])expect(()=>evidenceReadinessSchema.parse(value)).toThrow();
  });
});

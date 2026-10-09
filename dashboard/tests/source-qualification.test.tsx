import {afterEach,describe,it,expect,vi} from 'vitest';
import {readFileSync} from 'node:fs';
import {cleanup,render,screen} from '@testing-library/react';
import {SourceQualification} from '@/industry-forecast/SourceQualification';
import {fetchSourceQualification,sourceQualificationSchema} from '@/industry-forecast/qualification-client';

vi.mock('@/industry-forecast/qualification-client',async importOriginal=>({...await importOriginal<object>(),fetchSourceQualification:vi.fn()}));
const record=JSON.parse(readFileSync('../reports/research/swl1_source_qualification/final-readiness.json','utf8'));
afterEach(()=>{cleanup();vi.clearAllMocks();});
describe('real source qualification',()=>{
  it('shows actual inventory, zero admission and actionable owner gaps',async()=>{
    vi.mocked(fetchSourceQualification).mockResolvedValue(sourceQualificationSchema.parse(record));render(<SourceQualification/>);
    expect(await screen.findByText(/已审查 12 类来源/)).toHaveTextContent('正式准入 0');
    expect(screen.getByText(/申万：确认分类/)).toBeInTheDocument();expect(screen.getByText(/尚未发送/)).toBeInTheDocument();
    expect(screen.queryByText('DATA_SOURCE_READY')).not.toBeInTheDocument();
  });
  it('keeps failure closed if reviewed evidence cannot be read',async()=>{
    vi.mocked(fetchSourceQualification).mockRejectedValue(new Error('tampered'));render(<SourceQualification/>);
    expect(await screen.findByRole('status')).toHaveTextContent('无法确认新增数据授权');expect(screen.queryByText(/正式准入 0/)).not.toBeInTheDocument();
  });
  it('rejects forged readiness, source promotion, count mismatches and private fields',()=>{
    for(const value of [{...record,real_sources_admitted:1},{...record,research_readiness:'DATA_SOURCE_READY'},{...record,production_authority:'SYNTHETIC_PASS'},{...record,current_sources_audited:999},{...record,numeric_qa_run:true},{...record,raw_prices:[1]},{...record,owner_actions:[{...record.owner_actions[0],packet:'../../private'}]}])expect(()=>sourceQualificationSchema.parse(value)).toThrow();
  });
});

import { describe,expect,it } from 'vitest';
import { render,screen } from '@testing-library/react';
import { StatusBadge,PhaseBadge,SimulationBadge } from '@/etf-quant/components/StatusBadge';
import { MetricCard } from '@/etf-quant/components/MetricCard';
import { fmtMoney,fmtNum,fmtPct,fmtSigned,fmtSignedPct,fmtText,gainLossClass } from '@/etf-quant/format';
import { EmptyState,ErrorState } from '@/components/ui/states';
import { ResearchApiError } from '@/api/errors';

describe('StatusBadge status mapping',()=>{
  it('maps every gate status to a distinct label and keeps the raw code',()=>{
    render(<div>
      <StatusBadge status="PASS"/><StatusBadge status="BLOCKED"/><StatusBadge status="NOT_REACHED"/>
      <StatusBadge status="DEFERRED"/><StatusBadge status="UNKNOWN"/>
    </div>);
    expect(screen.getByText('通过')).toBeInTheDocument();
    expect(screen.getByText('阻断')).toBeInTheDocument();
    expect(screen.getByText('未达成')).toBeInTheDocument();
    expect(screen.getByText('暂缓')).toBeInTheDocument();
    expect(screen.getByText('未知')).toBeInTheDocument();
    for(const code of ['PASS','BLOCKED','NOT_REACHED','DEFERRED','UNKNOWN']) {
      expect(screen.getByText(code)).toBeInTheDocument();
    }
  });
  it('DEFERRED never uses failure styling',()=>{
    const {container}=render(<StatusBadge status="DEFERRED"/>);
    const badge=container.querySelector('span')!;
    expect(badge.className).toContain('bg-info/15');
    expect(badge.className).not.toContain('bg-destructive');
  });
  it('unrecognised status strings degrade to UNKNOWN honestly',()=>{
    render(<StatusBadge status="SOME_FUTURE_STATUS"/>);
    expect(screen.getByText('未知')).toBeInTheDocument();
    expect(screen.getByText('SOME_FUTURE_STATUS')).toBeInTheDocument();
  });
  it('PhaseBadge highlights blocked phases and SimulationBadge stays prominent',()=>{
    const {container}=render(<div><PhaseBadge phase="MAPPING_ADMISSION_BLOCKED"/><SimulationBadge/></div>);
    expect(container.textContent).toContain('MAPPING_ADMISSION_BLOCKED');
    expect(screen.getByText(/SIMULATION_ONLY/).className).toContain('bg-warning/15');
  });
});

describe('ETF formatters',()=>{
  it('never renders raw null / undefined / NaN',()=>{
    expect(fmtMoney(null)).toBe('—');
    expect(fmtNum(Number.NaN)).toBe('—');
    expect(fmtPct(undefined)).toBe('—');
    expect(fmtSigned(null)).toBe('—');
    expect(fmtText('')).toBe('—');
    expect(fmtText(null)).toBe('—');
  });
  it('formats money, percents and signed values',()=>{
    expect(fmtMoney('10000')).toBe('¥10,000.00');
    expect(fmtPct(0.0181)).toBe('1.81%');
    expect(fmtSignedPct(0.0181)).toBe('+1.81%');
    expect(fmtSignedPct(-0.02)).toBe('-2.00%');
    expect(fmtSigned(-0.01)).toBe('-0.01');
    expect(fmtSigned(0.02)).toBe('+0.02');
  });
  it('separates gain/loss colouring from status colouring (A-share red-up green-down)',()=>{
    expect(gainLossClass(0.5)).toBe('text-gain');
    expect(gainLossClass(-0.5)).toBe('text-loss');
    expect(gainLossClass(0)).toBe('text-foreground');
    expect(gainLossClass(null)).toBe('text-foreground');
  });
});

describe('MetricCard',()=>{
  it('renders label, formatted value and context hint',()=>{
    render(<MetricCard label="数据截止日" value="2026-09-24" hint="最近更新 2026-09-24T18:00" tone="success"/>);
    expect(screen.getByText('数据截止日')).toBeInTheDocument();
    expect(screen.getByText('2026-09-24')).toBeInTheDocument();
    expect(screen.getByText('最近更新 2026-09-24T18:00')).toBeInTheDocument();
  });
  it('honest placeholder for missing values',()=>{
    render(<MetricCard label="现金（CNY）" value={fmtMoney(null)}/>);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('shared states',()=>{
  it('EmptyState renders title and description',()=>{
    render(<EmptyState title="Shadow 尚未启动" description="没有 epoch，因此没有持仓。"/>);
    expect(screen.getByText('Shadow 尚未启动')).toBeInTheDocument();
    expect(screen.getByText('没有 epoch，因此没有持仓。')).toBeInTheDocument();
  });
  it('ErrorState renders a human message with retry, never a stack trace',()=>{
    render(<ErrorState error={new ResearchApiError('INTEGRITY_MISMATCH')} onRetry={()=>{}}/>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'重试'})).toBeInTheDocument();
  });
});

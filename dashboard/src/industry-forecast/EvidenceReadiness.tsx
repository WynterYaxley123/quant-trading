import { useResource } from '@/hooks/useResource';
import { fetchEvidenceReadiness } from './evidence-client';
import { SourceQualification } from './SourceQualification';

export function EvidenceReadiness() {
  const resource=useResource(fetchEvidenceReadiness,[]);
  return <section className="rounded-xl border bg-card p-5" aria-label="科研数据与证据准备">
    <h2 className="text-lg font-semibold">科研数据与证据准备 · Evidence readiness</h2>
    {resource.loading?<p>正在读取准备状态…</p>:resource.error?<p role="alert">准备状态暂不可用；无法确认来源准入。</p>:resource.data?<>
      <p className="mt-2">下一代研究：暂缓。先补齐数据使用权、当时可得性与正式授权身份。</p>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div><dt>既有一级模型</dt><dd>V1 / V2：Validation 失败，保持冻结</dd></div>
        <div><dt>数据来源准入</dt><dd>授权证明不足 · BLOCKED_UNVERIFIED_RIGHTS</dd></div>
        <div><dt>历史成员证据</dt><dd>重建 Tier C；当时公布证明未建立</dd></div>
        <div><dt>旧数值访问隔离</dt><dd>NOT_CERTIFIED · 可认证未见交易日 0</dd></div>
        <div><dt>新证据基础设施</dt><dd>合成验收通过；Linux Docker 隔离通过</dd></div>
        <div><dt>平台与授权限制</dt><dd>Windows 原生进程隔离、正式签名身份尚未建立</dd></div>
        <div><dt>未来研究协议</dt><dd>NOT_CREATED · 尚未创建</dd></div>
        <div><dt>正式前瞻证据</dt><dd>NONE · 观察 0，预测 0</dd></div>
      </dl>
      <p className="mt-3 text-sm">{resource.data.maturity.map(m=>`H${m.horizon}：待成熟，${m.matured_observations} 条`).join(' · ')}</p>
    </>:null}
    <SourceQualification/>
  </section>;
}

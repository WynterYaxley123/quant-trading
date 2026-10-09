import { useResource } from '@/hooks/useResource';
import { fetchSourceQualification } from './qualification-client';

const ownerItems:Record<string,string>={
  OWNER_SWS:'申万：确认分类、成分和官方指数的数据使用权，并取得历史公布与接收证明。',
  OWNER_TDX:'通达信：确认获准使用的接口，以及行情和公司行动的研究、保存与派生权限。',
  OWNER_SINA:'新浪：确认复权因子接口的使用范围与书面授权。',
  OWNER_BAOSTOCK:'BaoStock：确认数据许可、历史版本与完整上市退市覆盖。',
  OWNER_AUTHORITY:'确定正式准入审批人、签名身份管理和长期证据保管方案。',
};
export function SourceQualification() {
  const resource=useResource(fetchSourceQualification,[]);
  return <div className="mt-4 border-t pt-4" aria-label="真实数据来源审查">
    <h3 className="font-semibold">真实数据来源审查</h3>
    {resource.loading?<p>正在读取来源审查…</p>:resource.error?<p role="status">来源审查暂不可用；无法确认新增数据授权。</p>:resource.data?<>
      <p className="mt-2">已审查 {resource.data.current_sources_audited} 类来源，核验 {resource.data.official_documents_verified} 份公开材料；正式准入 {resource.data.real_sources_admitted} 个来源。</p>
      <p className="mt-2 text-sm">数据使用权、历史当时可得证据和事实质量仍待确认。官方一级指数数据与正式授权身份尚未建立，下一代研究继续暂缓。</p>
      <details className="mt-3"><summary>查看来源清单</summary><ul className="mt-2 list-disc pl-5 text-sm">{resource.data.sources.map(source=><li key={source.source_id}>{source.provider} · {source.dataset} · 待准入</li>)}</ul></details>
      <h4 className="mt-3 font-medium">需要你处理的事项</h4>
      <ul className="mt-2 list-disc pl-5 text-sm">{resource.data.owner_actions.map(action=><li key={action.id}>{ownerItems[action.id]??action.action}</li>)}</ul>
      <p className="mt-2 text-sm">供应商请求材料已备好，尚未发送；合同、采购和新的授权承诺需另行批准。</p>
    </>:null}
  </div>;
}

import { createRoute } from '@tanstack/react-router';
import { lazy,Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { LoadingState } from '@/components/ui/states';
import type { EtfSection } from '@/etf-quant/Pages';
const Page=lazy(()=>import('@/etf-quant/Pages').then(m=>({default:m.EtfQuantPage})));
function route<const TPath extends string>(path:TPath,section:EtfSection) {
  return createRoute({getParentRoute:()=>rootRoute,path,component:()=>
    <Suspense fallback={<LoadingState label="正在加载 ETF Quant 页面"/>}><Page section={section}/></Suspense>});
}
export const etfQuantRoutes=[route('/etf-quant/overview','overview'),route('/etf-quant/readiness','readiness'),route('/etf-quant/portfolio','portfolio'),
  route('/etf-quant/rankings','rankings'),route('/etf-quant/factors','factors'),route('/etf-quant/mappings','mappings'),
  route('/etf-quant/trades','trades'),route('/etf-quant/benchmarks','benchmarks'),route('/etf-quant/health','health')];

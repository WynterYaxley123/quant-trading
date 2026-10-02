import { createContext,useContext,type ReactNode } from 'react';
import { useResource } from '@/hooks/useResource';
import { getEtfQuantPort, EtfQuantDataError } from './data-port';
import type { EtfQuantStatus } from './contracts';

const Context=createContext<{etfQuant:boolean;status:EtfQuantStatus|null;loading:boolean;error:Error|null}>({etfQuant:false,status:null,loading:true,error:null});
export function EtfQuantProvider({children}:{children:ReactNode}) {
  const port=getEtfQuantPort();
  const status=useResource(async signal=>{
    try { return {value:await port.getStatus(signal),error:null}; }
    catch(error) { return {value:null,error:error instanceof Error ? error : new Error('ETF status failed')}; }
  },[port]);
  return <Context.Provider value={{etfQuant:!!status.data?.value,status:status.data?.value ?? null,loading:status.loading,error:status.data?.error ?? status.error}}>{children}</Context.Provider>;
}
export function useEtfQuantCapability(){return useContext(Context);}
export function etfServiceState(loading:boolean,status:EtfQuantStatus|null,error:Error|null) {
  if(loading) return 'CHECKING';
  if(error) return error instanceof EtfQuantDataError && error.code==='UNREACHABLE' ? 'DISCONNECTED' : 'DEGRADED';
  return status ? 'READY' : 'DEGRADED';
}

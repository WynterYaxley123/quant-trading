import { createContext,useContext,type ReactNode } from 'react';
import { useResource } from '@/hooks/useResource';
import { getEtfQuantPort } from './data-port';
import type { EtfQuantStatus } from './contracts';

const Context=createContext<{etfQuant:boolean;status:EtfQuantStatus|null}>({etfQuant:false,status:null});
export function EtfQuantProvider({children}:{children:ReactNode}) {
  const port=getEtfQuantPort();
  const status=useResource(signal=>port.getStatus(signal),[port]);
  return <Context.Provider value={{etfQuant:!!status.data,status:status.data}}>{children}</Context.Provider>;
}
export function useEtfQuantCapability(){return useContext(Context);}

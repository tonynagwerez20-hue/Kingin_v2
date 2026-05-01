import { create } from 'zustand';

export type PanelType = 
  | 'overview' 
  | 'positions' 
  | 'trade-history' 
  | 'strategy-engine' 
  | 'risk-monitor' 
  | 'market-watch' 
  | 'system-logs' 
  | 'settings';

interface AppStore {
  activePanel: PanelType;
  setActivePanel: (panel: PanelType) => void;
  isWebSocketConnected: boolean;
  setWebSocketConnected: (connected: boolean) => void;
  systemStatus: 'LIVE' | 'OFFLINE' | 'WARNING';
  setSystemStatus: (status: 'LIVE' | 'OFFLINE' | 'WARNING') => void;
  notificationCount: number;
  setNotificationCount: (count: number) => void;
  sidebarExpanded: boolean;
  setSidebarExpanded: (expanded: boolean) => void;
  autoRefreshEnabled: boolean;
  setAutoRefreshEnabled: (enabled: boolean) => void;
  refreshInterval: 1000 | 2000 | 5000; // milliseconds
  setRefreshInterval: (interval: 1000 | 2000 | 5000) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  activePanel: 'overview',
  setActivePanel: (panel: PanelType) => set({ activePanel: panel }),
  
  isWebSocketConnected: true,
  setWebSocketConnected: (connected: boolean) => set({ isWebSocketConnected: connected }),
  
  systemStatus: 'LIVE',
  setSystemStatus: (status: 'LIVE' | 'OFFLINE' | 'WARNING') => set({ systemStatus: status }),
  
  notificationCount: 0,
  setNotificationCount: (count: number) => set({ notificationCount: count }),
  
  sidebarExpanded: false,
  setSidebarExpanded: (expanded: boolean) => set({ sidebarExpanded: expanded }),
  
  autoRefreshEnabled: true,
  setAutoRefreshEnabled: (enabled: boolean) => set({ autoRefreshEnabled: enabled }),
  
  refreshInterval: 1000,
  setRefreshInterval: (interval: 1000 | 2000 | 5000) => set({ refreshInterval: interval }),
}));

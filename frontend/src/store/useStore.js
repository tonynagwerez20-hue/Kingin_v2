import { create } from 'zustand';
import api from '../api';

// Helper for generating mock data when backend is disconnected
const generateMockPrices = () => ({});

const useStore = create((set, get) => ({
  // --- CONNECTION STATE ---
  isApiReachable: false,
  isEngineRunning: false,
  isBridgeConnected: false,
  isInitializing: true,
  engineUptimeSeconds: 0,
  retryCount: 0,

  // --- ACCOUNT STATE ---
  account: {
    balance: 0,
    equity: 0,
    floatingPnl: 0,
    marginUsed: 0,
    marginPercent: 0,
    openPositions: 0,
    winRate: 0,
    todayPnl: 0,
  },
  equityHistory: [],

  // --- MARKET DATA ---
  prices: generateMockPrices(),
  prevPrices: generateMockPrices(),

  // --- TRADING DATA ---
  positions: [],
  signals: [],
  logs: [],
  
  // --- UI STATE ---
  activePanel: 'overview',
  sidebarExpanded: false,

  // --- ACTIONS ---
  setActivePanel: (panel) => set({ activePanel: panel }),
  toggleSidebar: () => set((state) => ({ sidebarExpanded: !state.sidebarExpanded }),),
  
  setConnected: (val) => set({ isApiReachable: val }),
  
  // Update state from API
  syncWithEngine: async () => {
    try {
      const res = await api.get('/engine/state');
      const data = res.data;
      
      // Map signals from backend flat state if not provided as array
      const currentSignal = data.signal_action && data.signal_action !== 'WAITING' ? [{
        symbol: data.symbol || 'XAUUSD',
        side: data.bias === 'BULLISH' ? 'BUY' : 'SELL',
        price: data.entry_price,
        score: Math.round((data.confluence_score || 0) * 100),
        time: Date.now(),
      }] : [];

      // Convert backend pipeline_log strings to frontend log objects
      const backendLogs = (data.pipeline_log || []).map((line) => ({
        time: Date.now(),
        level: line.includes('[ERROR]') ? 'ERROR' : line.includes('[WARN]') ? 'WARN' : 'INFO',
        module: 'ENGINE',
        message: line,
      }));

      set((state) => {
        const newEquity = Number(data.account_equity) || 0;
        const newHistory = [...state.equityHistory, { time: new Date().toLocaleTimeString(), equity: newEquity }].slice(-60);
        
        return {
          isApiReachable: true,
          isEngineRunning: data.running || false,
          isBridgeConnected: data.bridge_connected || false,
          isInitializing: false,
          engineUptimeSeconds: Number(data.engine_uptime_seconds) || 0,
          account: {
            ...state.account,
            balance: Number(data.account_balance) || 0,
            equity: newEquity,
            floatingPnl: Number(data.floating_pnl) || 0,
            openPositions: Number(data.open_trades_count) || 0,
            regime: data.regime || 'STABLE',
            bias: data.bias || 'NEUTRAL',
            killzone: data.killzone || 'N/A',
          },
          equityHistory: newHistory,
          positions: Array.isArray(data.positions) ? data.positions : [],
          signals: currentSignal.length > 0 ? currentSignal : state.signals,
          layers: Array.isArray(data.layers) ? data.layers : state.layers || [],
          logs: backendLogs.length > 0 ? backendLogs : state.logs,
        };
      });
    } catch (err) {
      set({ isApiReachable: false, isEngineRunning: false });
    }
  },

  startEngine: async () => {
    try {
      await api.post('/engine/start');
      set({ isEngineRunning: true });
    } catch (err) {
      console.error('Failed to start engine', err);
    }
  },

  stopEngine: async () => {
    try {
      await api.post('/engine/stop');
      set({ isEngineRunning: false });
    } catch (err) {
      console.error('Failed to stop engine', err);
    }
  },

  addLog: (level, module, message) => set((state) => ({
    logs: [{ time: Date.now(), level, module, message }, ...state.logs].slice(0, 200)
  })),
}));

export default useStore;

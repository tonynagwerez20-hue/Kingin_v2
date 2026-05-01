// KingIn Dashboard - Professional Trading Control Room
// Complete implementation with all 8 panels

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import './kingin.css';

// =============================================================================
// FORMATTERS
// =============================================================================

const formatCurrency = (n) => {
  if (n === null || n === undefined) return '$0.00';
  return n < 0 ? `-$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatPrice = (n, decimals = 5) => {
  if (n === null || n === undefined) return '0.00000';
  return n.toFixed(decimals);
};

const formatPercent = (n, showSign = true) => {
  if (n === null || n === undefined) return '0.00%';
  const sign = showSign && n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
};

const formatDuration = (ms) => {
  if (!ms) return '0m';
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${seconds}s`;
};

const formatTime = (date) => {
  if (!date) return '--:--:--';
  const d = new Date(date);
  return d.toLocaleTimeString('en-US', { hour12: false });
};

const formatDateTime = (date) => {
  if (!date) return '--/--/-- --:--';
  const d = new Date(date);
  return d.toLocaleString('en-US', { 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  });
};

const formatDate = (date) => {
  if (!date) return '--/--/----';
  const d = new Date(date);
  return d.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit' 
  });
};

// =============================================================================
// MOCK DATA
// =============================================================================

const generateMockPositions = () => {
  const baseTime = Date.now();
  return [
    { 
      ticket: 'TK001', 
      symbol: 'EURUSD', 
      direction: 'BUY', 
      volume: 1.0, 
      openPrice: 1.08432, 
      currentPrice: 1.08512,
      openTime: baseTime - 8124000,
      sl: 1.08200,
      tp: 1.08800,
    },
    { 
      ticket: 'TK002', 
      symbol: 'GBPUSD', 
      direction: 'SELL', 
      volume: 0.5, 
      openPrice: 1.27384, 
      currentPrice: 1.27291,
      openTime: baseTime - 4320000,
      sl: 1.27600,
      tp: 1.27000,
    },
    { 
      ticket: 'TK003', 
      symbol: 'XAUUSD', 
      direction: 'BUY', 
      volume: 0.1, 
      openPrice: 2342.50, 
      currentPrice: 2345.20,
      openTime: baseTime - 2160000,
      sl: 2338.00,
      tp: 2360.00,
    },
    { 
      ticket: 'TK004', 
      symbol: 'USDJPY', 
      direction: 'SELL', 
      volume: 0.8, 
      openPrice: 148.523, 
      currentPrice: 148.412,
      openTime: baseTime - 7200000,
      sl: 148.800,
      tp: 148.100,
    },
    { 
      ticket: 'TK005', 
      symbol: 'AUDUSD', 
      direction: 'BUY', 
      volume: 0.3, 
      openPrice: 0.65842, 
      currentPrice: 0.65918,
      openTime: baseTime - 3600000,
      sl: 0.65500,
      tp: 0.66500,
    },
    { 
      ticket: 'TK006', 
      symbol: 'USDCAD', 
      direction: 'SELL', 
      volume: 0.6, 
      openPrice: 1.36452, 
      currentPrice: 1.36328,
      openTime: baseTime - 5400000,
      sl: 1.37000,
      tp: 1.35800,
    },
    { 
      ticket: 'TK007', 
      symbol: 'EURJPY', 
      direction: 'BUY', 
      volume: 0.4, 
      openPrice: 161.284, 
      currentPrice: 161.412,
      openTime: baseTime - 1800000,
      sl: 160.800,
      tp: 162.000,
    },
  ];
};

const generateTradeHistory = () => {
  const strategies = ['ScalpBot-v2', 'TrendFollower', 'BreakoutPro', 'GridMaster'];
  const symbols = ['EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'AUDUSD', 'USDCAD'];
  const history = [];
  const baseTime = Date.now() - 86400000 * 30;
  
  for (let i = 0; i < 50; i++) {
    const direction = Math.random() > 0.4 ? 'BUY' : 'SELL';
    const volume = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0][Math.floor(Math.random() * 6)];
    const symbol = symbols[Math.floor(Math.random() * symbols.length)];
    const openPrice = symbol === 'XAUUSD' ? 2000 + Math.random() * 500 : 0.6 + Math.random() * 0.8;
    const closePrice = openPrice * (1 + (Math.random() - 0.45) * 0.02);
    const pnl = volume * (closePrice - openPrice) * (direction === 'BUY' ? 1 : -1) * 100000;
    const closeTime = baseTime + i * 3600000 + Math.random() * 3600000;
    
    history.push({
      ticket: `TH${String(1000 + i).padStart(4, '0')}`,
      symbol,
      direction,
      volume,
      openPrice: openPrice * (symbol === 'XAUUSD' ? 1 : 1),
      closePrice: closePrice * (symbol === 'XAUUSD' ? 1 : 1),
      openTime: closeTime - Math.random() * 7200000,
      closeTime,
      pnl,
      strategy: strategies[Math.floor(Math.random() * strategies.length)],
    });
  }
  
  return history.sort((a, b) => b.closeTime - a.closeTime);
};

const generateStrategies = () => [
  { 
    id: 1, 
    name: 'ScalpBot-v2', 
    status: 'RUNNING', 
    symbol: 'EURUSD', 
    tf: 'M5', 
    trades: 12, 
    winRate: 75, 
    pnl: 142.30, 
    cpu: 67,
    lastSignal: Date.now() - 120000,
    config: { maxSpread: 2, maxLoss: 50, lotSize: 0.01 },
    logs: [
      { time: Date.now() - 5000, level: 'INFO', message: 'Signal check completed' },
      { time: Date.now() - 30000, level: 'TRADE', message: 'Entry triggered at 1.08512' },
      { time: Date.now() - 35000, level: 'INFO', message: 'SL set at 1.08200' },
      { time: Date.now() - 60000, level: 'TRADE', message: 'TP modified to 1.08850' },
    ]
  },
  { 
    id: 2, 
    name: 'TrendFollower', 
    status: 'RUNNING', 
    symbol: 'GBPUSD', 
    tf: 'H1', 
    trades: 4, 
    winRate: 60, 
    pnl: 215.50, 
    cpu: 42,
    lastSignal: Date.now() - 1800000,
    config: { maxSpread: 3, maxLoss: 100, lotSize: 0.02 },
    logs: [
      { time: Date.now() - 120000, level: 'INFO', message: 'Checking trend on H1 timeframe' },
      { time: Date.now() - 300000, level: 'WARN', message: 'Low volatility detected' },
      { time: Date.now() - 600000, level: 'TRADE', message: 'Exit executed at 1.27291' },
    ]
  },
  { 
    id: 3, 
    name: 'BreakoutPro', 
    status: 'STOPPED', 
    symbol: 'XAUUSD', 
    tf: 'M15', 
    trades: 0, 
    winRate: 0, 
    pnl: 0, 
    cpu: 0,
    lastSignal: null,
    config: { maxSpread: 5, maxLoss: 200, lotSize: 0.05 },
    logs: [
      { time: Date.now() - 3600000, level: 'INFO', message: 'Strategy stopped by user' },
    ]
  },
  { 
    id: 4, 
    name: 'GridMaster', 
    status: 'ERROR', 
    symbol: 'USDJPY', 
    tf: 'M5', 
    trades: 8, 
    winRate: 50, 
    pnl: -45.20, 
    cpu: 89,
    lastSignal: Date.now() - 60000,
    config: { maxSpread: 2, maxLoss: 150, lotSize: 0.01 },
    logs: [
      { time: Date.now() - 10000, level: 'ERROR', message: 'Connection timeout - retrying' },
      { time: Date.now() - 30000, level: 'ERROR', message: 'API rate limit exceeded' },
      { time: Date.now() - 60000, level: 'WARN', message: 'High latency detected' },
    ]
  },
];

const generateMarketPrices = () => ({
  EURUSD: { bid: 1.08512, ask: 1.08514, spread: 2, change: 0.00182, changePercent: 0.17, high: 1.08650, low: 1.08320, volume: 125000 },
  GBPUSD: { bid: 1.27291, ask: 1.27293, spread: 2, change: -0.00251, changePercent: -0.20, high: 1.27600, low: 1.27150, volume: 85000 },
  XAUUSD: { bid: 2345.18, ask: 2345.22, spread: 4, change: 12.50, changePercent: 0.54, high: 2352.00, low: 2338.00, volume: 45000 },
  USDJPY: { bid: 148.412, ask: 148.418, spread: 6, change: 0.842, changePercent: 0.57, high: 148.900, low: 147.800, volume: 92000 },
  AUDUSD: { bid: 0.65918, ask: 0.65922, spread: 4, change: 0.00124, changePercent: 0.19, high: 0.66100, low: 0.65750, volume: 38000 },
  USDCAD: { bid: 1.36328, ask: 1.36332, spread: 4, change: -0.00145, changePercent: -0.11, high: 1.36500, low: 1.36200, volume: 52000 },
});

const generateRiskMetrics = () => ({
  dailyLossLimit: { current: 340, limit: 500, percentage: 68 },
  maxDrawdown: { current: 3.2, limit: 10, percentage: 32 },
  marginUsage: { current: 1240, limit: 25000, percentage: 4.96 },
  exposure: { current: 12400, limit: 25000, percentage: 49.6 },
  exposureBySymbol: [
    { symbol: 'EURUSD', amount: 4200, percentage: 33.9 },
    { symbol: 'GBPUSD', amount: 2800, percentage: 22.6 },
    { symbol: 'XAUUSD', amount: 1900, percentage: 15.3 },
    { symbol: 'USDJPY', amount: 1800, percentage: 14.5 },
    { symbol: 'AUDUSD', amount: 900, percentage: 7.3 },
    { symbol: 'USDCAD', amount: 800, percentage: 6.5 },
  ],
  riskEvents: [
    { time: Date.now() - 300000, severity: 'INFO', message: 'Margin usage at 4.96%' },
    { time: Date.now() - 600000, severity: 'INFO', message: 'Daily loss limit at 68%' },
    { time: Date.now() - 1200000, severity: 'WARN', message: 'Strategy BreakoutPro has not traded in 1 hour' },
    { time: Date.now() - 1800000, severity: 'INFO', message: 'Portfolio exposure increased by $2,100' },
    { time: Date.now() - 3600000, severity: 'INFO', message: 'Risk check completed - all within limits' },
  ],
});

const generateSystemLogs = () => {
  const levels = ['INFO', 'INFO', 'INFO', 'INFO', 'WARN', 'ERROR', 'DEBUG', 'TRADE'];
  const modules = ['core', 'ws', 'api', 'risk', 'strategy', 'api', 'core'];
  const messages = [
    'WebSocket connection established',
    'Received tick update for EURUSD',
    'Strategy ScalpBot-v2 updated signal state',
    'Risk check passed',
    'Position TK001 updated P&L',
    'API request completed in 45ms',
    'Cache hit for market data',
    'New tick: EURUSD 1.08512/1.08514',
    'Strategy signal processed',
    'Position TK002 closed with profit',
    'WebSocket ping successful',
    'Market data refreshed',
    'Connection latency: 23ms',
  ];
  
  const logs = [];
  for (let i = 0; i < 100; i++) {
    const idx = Math.floor(Math.random() * levels.length);
    logs.push({
      time: Date.now() - i * 10000 - Math.random() * 5000,
      level: levels[idx],
      module: modules[idx % modules.length],
      message: messages[Math.floor(Math.random() * messages.length)],
    });
  }
  
  return logs.sort((a, b) => b.time - a.time);
};

const generateAlerts = () => [
  { time: Date.now() - 60000, severity: 'INFO', message: 'Strategy ScalpBot-v2 triggered entry signal' },
  { time: Date.now() - 120000, severity: 'INFO', message: 'Position TK003 opened: BUY 0.10 XAUUSD @ 2342.50' },
  { time: Date.now() - 180000, severity: 'WARN', message: 'GridMaster: High latency detected (150ms)' },
  { time: Date.now() - 300000, severity: 'INFO', message: 'Daily risk check completed - all within limits' },
  { time: Date.now() - 360000, severity: 'INFO', message: 'Position TK002 TP hit: +$46.50' },
  { time: Date.now() - 420000, severity: 'WARN', message: 'BreakoutPro: No trades for 30 minutes' },
  { time: Date.now() - 600000, severity: 'INFO', message: 'Market data refresh completed' },
  { time: Date.now() - 720000, severity: 'INFO', message: 'Session P&L: +$270.80' },
  { time: Date.now() - 900000, severity: 'ERROR', message: 'Connection timeout - reconnected after 5s' },
  { time: Date.now() - 1200000, severity: 'INFO', message: 'Strategy TrendFollower opened new position' },
];

const generateEquityCurve = () => {
  const points = [];
  let base = 24000;
  for (let i = 7; i >= 0; i--) {
    base += (Math.random() - 0.3) * 150;
    points.push({
      date: new Date(Date.now() - i * 86400000).toISOString().split('T')[0],
      equity: base,
    });
  }
  return points;
};

// =============================================================================
// STATE MANAGEMENT
// =============================================================================

const useAppState = () => {
  const [activePanel, setActivePanel] = useState('overview');
  const [connectionStatus, setConnectionStatus] = useState('LIVE');
  const [notificationCount, setNotificationCount] = useState(3);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  
  return {
    activePanel,
    setActivePanel,
    connectionStatus,
    setConnectionStatus,
    notificationCount,
    setNotificationCount,
    sidebarExpanded,
    setSidebarExpanded,
  };
};

import api from './api';

const useEngineState = () => {
  const [engineState, setEngineState] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const fetchState = async () => {
      try {
        const res = await api.get('/engine/state');
        const state = res.data;
        if (!cancelled) {
          setEngineState(state);
          setConnected(true);
        }
      } catch (err) {
        if (!cancelled) {
          setConnected(false);
        }
      }
    };

    fetchState();
    const interval = setInterval(fetchState, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return { engineState, connected };
};

const usePositions = (engineState, connected) => {
  const [mockPositions] = useState(generateMockPositions());
  const [mockTick, setMockTick] = useState(0);

  const isApiReachable = connected;

  useEffect(() => {
    if (isApiReachable) return;
    const interval = setInterval(() => setMockTick(t => t + 1), 1000);
    return () => clearInterval(interval);
  }, [isApiReachable]);

  const positions = useMemo(() => {
    if (isApiReachable) {
      const raw = Array.isArray(engineState?.positions) ? engineState.positions : [];
      return raw.map((p, i) => ({
        ticket: p.ticket || `POS-${i + 1}`,
        symbol: p.symbol || 'XAUUSD',
        direction: (p.type || 'BUY').toUpperCase(),
        volume: Number(p.lots) || 0,
        openPrice: Number(p.open_price) || 0,
        currentPrice: Number(p.current_price) || Number(p.open_price) || 0,
        openTime: p.open_time ? new Date(p.open_time).getTime() : Date.now(),
        sl: Number(p.sl) || 0,
        tp: Number(p.tp) || 0,
        pnl: Number(p.floating_pnl) || 0,
      }));
    }
    return mockPositions.map(p => {
      const multiplier = p.symbol === 'XAUUSD' ? 100 : 100000;
      const drift = (Math.sin(mockTick * 0.1 + p.ticket.charCodeAt(0)) * 0.0001) *
        (p.symbol === 'XAUUSD' ? 10 : p.symbol === 'USDJPY' ? 10 : 1);
      const cp = p.currentPrice + drift;
      const priceDiff = p.direction === 'BUY' ? cp - p.openPrice : p.openPrice - cp;
      const pnl = priceDiff * p.volume * multiplier;
      return { ...p, currentPrice: cp, pnl };
    });
  }, [isApiReachable, engineState, mockPositions, mockTick]);

  const totalPnl = useMemo(() => positions.reduce((sum, p) => sum + p.pnl, 0), [positions]);

  return { positions, totalPnl };
};

const useAccountStats = (engineState, connected) => {
  const [mockStats] = useState({
    balance: 24831.50,
    equity: 25102.30,
    marginUsed: 1240.00,
    marginPercent: 4.96,
    todayPnl: 270.80,
    openPositions: 7,
    winRate: 68.4,
  });

  if (connected && engineState) {
    const balance = Number(engineState.account_balance) || 0;
    const equity = Number(engineState.account_equity) || 0;
    const floating = Number(engineState.floating_pnl) || 0;
    return {
      balance,
      equity: equity || (balance + floating),
      marginUsed: 0,
      marginPercent: 0,
      todayPnl: floating,
      openPositions: Number(engineState.open_trades_count) || 0,
      winRate: 0,
    };
  }

  return mockStats;
};

const useMarketPrices = () => {
  const [prices, setPrices] = useState(generateMarketPrices());
  const [prevPrices, setPrevPrices] = useState(generateMarketPrices());
  
  useEffect(() => {
    setPrevPrices(prices);
    const interval = setInterval(() => {
      setPrices(prev => {
        const updated = { ...prev };
        Object.keys(updated).forEach(symbol => {
          const spread = updated[symbol].spread / 100000;
          updated[symbol] = {
            ...updated[symbol],
            bid: updated[symbol].bid + (Math.random() - 0.5) * spread,
            ask: updated[symbol].ask + (Math.random() - 0.5) * spread,
            change: updated[symbol].change + (Math.random() - 0.5) * 0.001,
            changePercent: (prev[symbol]?.changePercent || 0) + (Math.random() - 0.5) * 0.01,
          };
        });
        return updated;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [prices]);
  
  const getFlashClass = (symbol, field) => {
    const curr = prices[symbol]?.[field];
    const prev = prevPrices[symbol]?.[field];
    if (!curr || !prev) return '';
    if (curr > prev) return 'flash-up';
    if (curr < prev) return 'flash-down';
    return '';
  };
  
  return { prices, getFlashClass };
};

const useStrategies = () => {
  const [strategies, setStrategies] = useState(generateStrategies());
  
  useEffect(() => {
    const interval = setInterval(() => {
      setStrategies(prev => prev.map(s => ({
        ...s,
        cpu: s.status === 'RUNNING' ? Math.min(100, s.cpu + (Math.random() - 0.5) * 10) : s.cpu,
      })));
    }, 2000);
    return () => clearInterval(interval);
  }, []);
  
  return strategies;
};

const useRiskMetrics = () => {
  const [metrics, setMetrics] = useState(generateRiskMetrics());
  
  return metrics;
};

const useSystemLogs = () => {
  const [logs, setLogs] = useState(generateSystemLogs());
  const [filter, setFilter] = useState({ level: 'ALL', module: 'ALL', search: '' });
  const [autoScroll, setAutoScroll] = useState(true);
  
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      if (filter.level !== 'ALL' && log.level !== filter.level) return false;
      if (filter.module !== 'ALL' && log.module !== filter.module) return false;
      if (filter.search && !log.message.toLowerCase().includes(filter.search.toLowerCase())) return false;
      return true;
    });
  }, [logs, filter]);
  
  return { logs: filteredLogs, filter, setFilter, autoScroll, setAutoScroll };
};

// =============================================================================
// COMPONENTS
// =============================================================================

const StatCard = ({ label, value, subvalue, trend, highlight }) => (
  <div className={`stat-card ${highlight ? 'highlight' : ''}`}>
    <div className="stat-label">{label}</div>
    <div className="stat-value">{value}</div>
    {subvalue && <div className="stat-sub">{subvalue}</div>}
    {trend !== undefined && (
      <div className={`stat-trend ${trend >= 0 ? 'positive' : 'negative'}`}>
        {trend >= 0 ? '↑' : '↓'} {formatPercent(trend)}
      </div>
    )}
  </div>
);

const SignalStatusBar = ({ engineState }) => {
  if (!engineState) return null;
  const signal = engineState.signal_action || 'WAITING';
  const bias = engineState.bias || 'NEUTRAL';
  const price = Number(engineState.current_price) || 0;
  const entry = Number(engineState.entry_price) || 0;
  const sl = Number(engineState.stop_loss) || 0;
  const tp = Number(engineState.take_profit) || 0;
  const score = Number(engineState.confluence_score) || 0;
  const kz = engineState.killzone || 'N/A';

  const signalColor = signal === 'BUY' ? '#00e87a' : signal === 'SELL' ? '#ff2d4e' : '#ffaa00';
  const biasColor = bias === 'BULLISH' ? '#00e87a' : bias === 'BEARISH' ? '#ff2d4e' : '#ffaa00';

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
      padding: '10px 16px', marginBottom: '16px',
      background: 'var(--kg-surface, #0d0d0d)',
      border: '1px solid var(--kg-border, #1a1a1a)',
      borderRadius: '6px', fontSize: '11px', fontFamily: 'inherit',
    }}>
      <span style={{ color: 'var(--kg-muted, #556)', letterSpacing: '1px' }}>LIVE SIGNAL</span>
      <span style={{ color: signalColor, fontWeight: 700, letterSpacing: '2px' }}>{signal}</span>
      <span style={{ color: 'var(--kg-muted, #556)' }}>|</span>
      <span style={{ color: 'var(--kg-muted, #556)' }}>BIAS</span>
      <span style={{ color: biasColor, fontWeight: 700 }}>{bias}</span>
      {price > 0 && <><span style={{ color: 'var(--kg-muted, #556)' }}>|</span><span style={{ color: '#aab' }}>PRICE <span style={{ color: '#dde' }}>${price.toFixed(2)}</span></span></>}
      {entry > 0 && <><span style={{ color: 'var(--kg-muted, #556)' }}>|</span><span style={{ color: '#aab' }}>ENTRY <span style={{ color: '#dde' }}>${entry.toFixed(2)}</span></span></>}
      {sl > 0 && <><span style={{ color: 'var(--kg-muted, #556)' }}>|</span><span style={{ color: '#aab' }}>SL <span style={{ color: '#ff2d4e' }}>${sl.toFixed(2)}</span></span></>}
      {tp > 0 && <><span style={{ color: 'var(--kg-muted, #556)' }}>|</span><span style={{ color: '#aab' }}>TP <span style={{ color: '#00e87a' }}>${tp.toFixed(2)}</span></span></>}
      {score > 0 && <><span style={{ color: 'var(--kg-muted, #556)' }}>|</span><span style={{ color: '#aab' }}>SCORE <span style={{ color: '#ffaa00' }}>{score.toFixed(1)}</span></span></>}
      {engineState.layer_results?.find(l => l.layer === 'MLFilterLayer') && (
        <>
          <span style={{ color: 'var(--kg-muted, #556)' }}>|</span>
          <span style={{ color: '#aab' }}>ML CONF <span style={{ color: '#00e87a' }}>
            {(engineState.layer_results.find(l => l.layer === 'MLFilterLayer').result.score * 100).toFixed(0)}%
          </span></span>
        </>
      )}
      {kz !== 'N/A' && <><span style={{ color: 'var(--kg-muted, #556)' }}>|</span><span style={{ color: '#aab' }}>KZ <span style={{ color: '#dde' }}>{kz}</span></span></>}

    </div>
  );
};

const OverviewPanel = ({ accountStats, positions, totalPnl, engineState }) => {
  const [equityCurve] = useState(generateEquityCurve);
  const [alerts] = useState(generateAlerts);
  
  const topPositions = positions.slice(0, 5);
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">Overview</h1>
          <p className="panel-subtitle">Real-time account and trading statistics</p>
        </div>
      </div>

      <SignalStatusBar engineState={engineState} />
      
      <div className="stat-grid">
        <StatCard label="BALANCE" value={formatCurrency(accountStats.balance)} subvalue="Account balance" highlight />
        <StatCard label="EQUITY" value={formatCurrency(accountStats.equity)} subvalue="Live equity" />
        <StatCard label="MARGIN USED" value={formatCurrency(accountStats.marginUsed)} subvalue={`${accountStats.marginPercent}% used`} />
        <StatCard label="TODAY P&L" value={formatCurrency(accountStats.todayPnl)} highlight />
        <StatCard label="OPEN TRADES" value={accountStats.openPositions} subvalue="live positions" />
        <StatCard label="WIN RATE" value={accountStats.winRate > 0 ? formatPercent(accountStats.winRate) : 'N/A'} subvalue="last 30d" />
      </div>
      
      <div className="two-col">
        <div className="two-col-main">
          <div className="chart-container">
            <div className="chart-header">
              <span className="chart-title">Equity Curve (7 Days)</span>
              <div className="chart-controls">
                {['1D', '7D', '1M', '3M'].map(tf => (
                  <button key={tf} className={`chart-btn ${tf === '7D' ? 'active' : ''}`}>{tf}</button>
                ))}
              </div>
            </div>
            <div style={{ height: 200, display: 'flex', alignItems: 'flex-end', gap: '2px', padding: '20px 0' }}>
              {equityCurve.map((point, i) => (
                <div key={i} style={{ 
                  flex: 1, 
                  height: `${((point.equity - 23500) / 500) * 100}%`, 
                  background: 'linear-gradient(180deg, var(--kg-gold), rgba(255, 215, 0, 0.3))',
                  borderRadius: '2px 2px 0 0',
                  minHeight: '20px',
                }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--kg-muted)' }}>
              {equityCurve.map((point, i) => (
                <span key={i}>{point.date.slice(5)}</span>
              ))}
            </div>
          </div>
        </div>
        
        <div className="two-col-side">
          <div className="data-table-container">
            <div className="chart-header">
              <span className="chart-title">Open Positions</span>
              <button className="btn btn-sm">View All →</button>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Dir</th>
                  <th>P&L</th>
                </tr>
              </thead>
              <tbody>
                {topPositions.map(p => (
                  <tr key={p.ticket}>
                    <td className="text">{p.symbol}</td>
                    <td><span className={`badge ${p.direction.toLowerCase()}`}>{p.direction}</span></td>
                    <td className={`pnl-value ${p.pnl >= 0 ? 'positive' : 'negative'}`}>
                      {p.pnl >= 0 ? '+' : ''}{formatCurrency(p.pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      
      <div className="data-table-container">
        <div className="chart-header">
          <span className="chart-title">Recent Alerts</span>
        </div>
        <div className="alerts-feed">
          {alerts.map((alert, i) => (
            <div key={i} className="alert-item">
              <span className="alert-time">{formatTime(alert.time)}</span>
              <span className={`alert-badge ${alert.severity.toLowerCase()}`}>{alert.severity}</span>
              <span className="alert-message">{alert.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const PositionsPanel = ({ positions }) => {
  const [sortField, setSortField] = useState('ticket');
  const [sortAsc, setSortAsc] = useState(true);
  const [filterSymbol, setFilterSymbol] = useState('');
  const [filterDir, setFilterDir] = useState('ALL');
  
  const sortedPositions = useMemo(() => {
    let filtered = [...positions];
    
    if (filterSymbol) {
      filtered = filtered.filter(p => p.symbol.toLowerCase().includes(filterSymbol.toLowerCase()));
    }
    if (filterDir !== 'ALL') {
      filtered = filtered.filter(p => p.direction === filterDir);
    }
    
    filtered.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      if (typeof aVal === 'string') {
        return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortAsc ? aVal - bVal : bVal - aVal;
    });
    
    return filtered;
  }, [positions, sortField, sortAsc, filterSymbol, filterDir]);
  
  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };
  
  const totalExposure = positions.reduce((sum, p) => sum + p.volume * p.openPrice * 100000, 0);
  const totalFloatingPnl = positions.reduce((sum, p) => sum + p.pnl, 0);
  const avgDuration = positions.reduce((sum, p) => sum + (Date.now() - p.openTime), 0) / positions.length;
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">Open Positions</h1>
          <p className="panel-subtitle">{positions.length} active positions • Last updated just now</p>
        </div>
      </div>
      
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Symbol</span>
          <input 
            type="text" 
            className="input" 
            placeholder="Search..."
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
            style={{ width: 120 }}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label">Direction</span>
          <select 
            className="select"
            value={filterDir}
            onChange={(e) => setFilterDir(e.target.value)}
          >
            <option value="ALL">All</option>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </select>
        </div>
      </div>
      
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('ticket')}>Ticket</th>
              <th className="sortable" onClick={() => handleSort('symbol')}>Symbol</th>
              <th className="sortable" onClick={() => handleSort('direction')}>Dir</th>
              <th className="sortable" onClick={() => handleSort('volume')}>Volume</th>
              <th className="sortable" onClick={() => handleSort('openPrice')}>Open Price</th>
              <th>Current</th>
              <th>SL</th>
              <th>TP</th>
              <th>Duration</th>
              <th className="sortable" onClick={() => handleSort('pnl')}>P&L</th>
            </tr>
          </thead>
          <tbody>
            {sortedPositions.map(p => (
              <tr key={p.ticket}>
                <td className="text">{p.ticket}</td>
                <td className="text">{p.symbol}</td>
                <td><span className={`badge ${p.direction.toLowerCase()}`}>{p.direction}</span></td>
                <td>{p.volume.toFixed(2)}</td>
                <td>{formatPrice(p.openPrice, p.symbol === 'XAUUSD' ? 2 : 5)}</td>
                <td>{formatPrice(p.currentPrice, p.symbol === 'XAUUSD' ? 2 : 5)}</td>
                <td>{formatPrice(p.sl, p.symbol === 'XAUUSD' ? 2 : 5)}</td>
                <td>{formatPrice(p.tp, p.symbol === 'XAUUSD' ? 2 : 5)}</td>
                <td>{formatDuration(Date.now() - p.openTime)}</td>
                <td className={`pnl-value ${p.pnl >= 0 ? 'positive' : 'negative'}`}>
                  {p.pnl >= 0 ? '+' : ''}{formatCurrency(p.pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        <div className="footer-summary">
          <div className="footer-stat">
            <span className="footer-stat-label">Total Exposure:</span>
            <span className="footer-stat-value">{formatCurrency(totalExposure)}</span>
          </div>
          <div className="footer-stat">
            <span className="footer-stat-label">Floating P&L:</span>
            <span className={`footer-stat-value ${totalFloatingPnl >= 0 ? 'positive' : 'negative'}`}>
              {totalFloatingPnl >= 0 ? '+' : ''}{formatCurrency(totalFloatingPnl)}
            </span>
          </div>
          <div className="footer-stat">
            <span className="footer-stat-label">Avg Duration:</span>
            <span className="footer-stat-value">{formatDuration(avgDuration)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const TradeHistoryPanel = () => {
  const [history] = useState(generateTradeHistory);
  const [filter, setFilter] = useState({ symbol: '', direction: 'ALL', strategy: 'ALL', from: '', to: '' });
  const [page, setPage] = useState(0);
  
  const filteredHistory = useMemo(() => {
    return history.filter(h => {
      if (filter.symbol && !h.symbol.toLowerCase().includes(filter.symbol.toLowerCase())) return false;
      if (filter.direction !== 'ALL' && h.direction !== filter.direction) return false;
      if (filter.strategy !== 'ALL' && h.strategy !== filter.strategy) return false;
      return true;
    });
  }, [history, filter]);
  
  const pageSize = 25;
  const pageData = filteredHistory.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(filteredHistory.length / pageSize);
  
  const totalProfit = filteredHistory.filter(h => h.pnl > 0).reduce((sum, h) => sum + h.pnl, 0);
  const totalLoss = filteredHistory.filter(h => h.pnl < 0).reduce((sum, h) => sum + Math.abs(h.pnl), 0);
  const netPnl = filteredHistory.reduce((sum, h) => sum + h.pnl, 0);
  const winRate = filteredHistory.length > 0 ? (filteredHistory.filter(h => h.pnl > 0).length / filteredHistory.length * 100) : 0;
  
  const uniqueStrategies = [...new Set(history.map(h => h.strategy))];
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">Trade History</h1>
          <p className="panel-subtitle">{filteredHistory.length} closed trades</p>
        </div>
        <div className="panel-actions">
          <button className="btn btn-sm">Export CSV</button>
        </div>
      </div>
      
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Symbol</span>
          <input type="text" className="input" placeholder="Search..." value={filter.symbol} onChange={(e) => setFilter({ ...filter, symbol: e.target.value })} style={{ width: 100 }} />
        </div>
        <div className="filter-group">
          <span className="filter-label">Direction</span>
          <select className="select" value={filter.direction} onChange={(e) => setFilter({ ...filter, direction: e.target.value })}>
            <option value="ALL">All</option>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </select>
        </div>
        <div className="filter-group">
          <span className="filter-label">Strategy</span>
          <select className="select" value={filter.strategy} onChange={(e) => setFilter({ ...filter, strategy: e.target.value })}>
            <option value="ALL">All</option>
            {uniqueStrategies.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
      
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Close Time</th>
              <th>Ticket</th>
              <th>Symbol</th>
              <th>Dir</th>
              <th>Vol</th>
              <th>Open</th>
              <th>Close</th>
              <th>P&L</th>
              <th>Strategy</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map(h => (
              <tr key={h.ticket}>
                <td className="text">{formatDateTime(h.closeTime)}</td>
                <td className="text">{h.ticket}</td>
                <td className="text">{h.symbol}</td>
                <td><span className={`badge ${h.direction.toLowerCase()}`}>{h.direction}</span></td>
                <td>{h.volume.toFixed(2)}</td>
                <td>{formatPrice(h.openPrice, h.symbol === 'XAUUSD' ? 2 : 5)}</td>
                <td>{formatPrice(h.closePrice, h.symbol === 'XAUUSD' ? 2 : 5)}</td>
                <td className={`pnl-value ${h.pnl >= 0 ? 'positive' : 'negative'}`}>
                  {h.pnl >= 0 ? '+' : ''}{formatCurrency(h.pnl)}
                </td>
                <td className="text">{h.strategy}</td>
                <td>{formatDuration(h.closeTime - h.openTime)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        
        <div className="pagination">
          <div className="pagination-info">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, filteredHistory.length)} of {filteredHistory.length}
          </div>
          <div className="pagination-controls">
            <button className="pagination-btn" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <button className="pagination-btn" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        </div>
        
        <div className="footer-summary">
          <div className="footer-stat">
            <span className="footer-stat-label">Total Trades:</span>
            <span className="footer-stat-value">{filteredHistory.length}</span>
          </div>
          <div className="footer-stat">
            <span className="footer-stat-label">Total Profit:</span>
            <span className="footer-stat-value positive">{formatCurrency(totalProfit)}</span>
          </div>
          <div className="footer-stat">
            <span className="footer-stat-label">Total Loss:</span>
            <span className="footer-stat-value negative">{formatCurrency(totalLoss)}</span>
          </div>
          <div className="footer-stat">
            <span className="footer-stat-label">Net P&L:</span>
            <span className={`footer-stat-value ${netPnl >= 0 ? 'positive' : 'negative'}`}>{formatCurrency(netPnl)}</span>
          </div>
          <div className="footer-stat">
            <span className="footer-stat-label">Win Rate:</span>
            <span className="footer-stat-value">{winRate.toFixed(1)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const StrategyEnginePanel = ({ strategies }) => {
  const [expandedLog, setExpandedLog] = useState(null);
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">Strategy Engine</h1>
          <p className="panel-subtitle">Last heartbeat: just now</p>
        </div>
      </div>
      
      <div className="strategy-grid">
        {strategies.map(s => (
          <div key={s.id} className={`strategy-card status-${s.status.toLowerCase()}`}>
            <div className="strategy-card-header">
              <div className="strategy-card-title">
                {s.status === 'RUNNING' && <div className="status-dot" />}
                <h3>{s.name}</h3>
                <span className={`badge ${s.status.toLowerCase()}`}>{s.status}</span>
              </div>
              <button className="strategy-card-menu">⋯</button>
            </div>
            
            <div className="strategy-card-info">
              <div className="strategy-card-info-item">
                <span>Symbol:</span>
                <span className="value">{s.symbol}</span>
              </div>
              <div className="strategy-card-info-item">
                <span>Timeframe:</span>
                <span className="value">{s.tf}</span>
              </div>
              <div className="strategy-card-info-item">
                <span>Trades today:</span>
                <span className="value">{s.trades}</span>
              </div>
              <div className="strategy-card-info-item">
                <span>Win Rate:</span>
                <span className="value">{s.winRate}%</span>
              </div>
              <div className="strategy-card-info-item">
                <span>Session P&L:</span>
                <span className={`value ${s.pnl >= 0 ? 'positive' : 'negative'}`}>
                  {s.pnl >= 0 ? '+' : ''}{formatCurrency(s.pnl)}
                </span>
              </div>
              <div className="strategy-card-info-item">
                <span>Last signal:</span>
                <span className="value">{s.lastSignal ? formatDuration(Date.now() - s.lastSignal) : 'N/A'}</span>
              </div>
            </div>
            
            <div className="strategy-card-cpu">
              <div className="strategy-card-cpu-label">
                <span>CPU</span>
                <span>{Math.round(s.cpu)}%</span>
              </div>
              <div className="cpu-bar">
                <div className="cpu-bar-fill" style={{ width: `${s.cpu}%` }} />
              </div>
            </div>
            
            <div className="strategy-card-log">
              {s.logs.slice(0, 3).map((log, i) => (
                <div key={i}>
                  <span style={{ color: 'var(--kg-muted)' }}>[{formatTime(log.time)}]</span>{' '}
                  <span className={`log-level ${log.level.toLowerCase()}`}>{log.level}</span>{' '}
                  {log.message}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const RiskMonitorPanel = ({ metrics }) => {
  const getGaugeClass = (pct) => {
    if (pct >= 80) return 'danger';
    if (pct >= 60) return 'warning';
    return 'safe';
  };
  
  const riskLevel = metrics.maxDrawdown.percentage >= 80 ? 'CRITICAL' : 
                metrics.dailyLossLimit.percentage >= 80 ? 'HIGH' : 
                metrics.dailyLossLimit.percentage >= 60 ? 'MEDIUM' : 'LOW';
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">Risk Monitor</h1>
          <p className="panel-subtitle">Real-time risk assessment</p>
        </div>
        <span className={`badge ${riskLevel.toLowerCase()}`}>{riskLevel}</span>
      </div>
      
      <div className="risk-grid">
        <div className="risk-gauge">
          <div className="risk-gauge-header">
            <span className="risk-gauge-title">Daily Loss Limit</span>
            <span className={`risk-gauge-value ${getGaugeClass(metrics.dailyLossLimit.percentage)}`}>
              {metrics.dailyLossLimit.percentage >= 60 ? '⚠' : '✓'} {metrics.dailyLossLimit.percentage}%
            </span>
          </div>
          <div className="risk-gauge-bar">
            <div className={`risk-gauge-fill ${getGaugeClass(metrics.dailyLossLimit.percentage)}`} style={{ width: `${metrics.dailyLossLimit.percentage}%` }} />
          </div>
          <div className="risk-gauge-markers">
            <span>{formatCurrency(metrics.dailyLossLimit.current)}</span>
            <span>{formatCurrency(metrics.dailyLossLimit.limit)} limit</span>
          </div>
        </div>
        
        <div className="risk-gauge">
          <div className="risk-gauge-header">
            <span className="risk-gauge-title">Max Drawdown</span>
            <span className={`risk-gauge-value ${getGaugeClass(metrics.maxDrawdown.percentage)}`}>
              {metrics.maxDrawdown.percentage >= 60 ? '⚠' : '✓'} {metrics.maxDrawdown.percentage}%
            </span>
          </div>
          <div className="risk-gauge-bar">
            <div className={`risk-gauge-fill ${getGaugeClass(metrics.maxDrawdown.percentage)}`} style={{ width: `${metrics.maxDrawdown.percentage * 10}%` }} />
          </div>
          <div className="risk-gauge-markers">
            <span>{metrics.maxDrawdown.current}%</span>
            <span>{metrics.maxDrawdown.limit}% limit</span>
          </div>
        </div>
        
        <div className="risk-gauge">
          <div className="risk-gauge-header">
            <span className="risk-gauge-title">Margin Usage</span>
            <span className={`risk-gauge-value ${getGaugeClass(metrics.marginUsage.percentage)}`}>
              {metrics.marginUsage.percentage >= 60 ? '⚠' : '✓'} {metrics.marginUsage.percentage}%
            </span>
          </div>
          <div className="risk-gauge-bar">
            <div className={`risk-gauge-fill ${getGaugeClass(metrics.marginUsage.percentage)}`} style={{ width: `${metrics.marginUsage.percentage}%` }} />
          </div>
          <div className="risk-gauge-markers">
            <span>{formatCurrency(metrics.marginUsage.current)}</span>
            <span>{formatCurrency(metrics.marginUsage.limit)} limit</span>
          </div>
        </div>
        
        <div className="risk-gauge">
          <div className="risk-gauge-header">
            <span className="risk-gauge-title">Total Exposure</span>
            <span className={`risk-gauge-value ${getGaugeClass(metrics.exposure.percentage)}`}>
              {metrics.exposure.percentage >= 60 ? '⚠' : '✓'} {metrics.exposure.percentage}%
            </span>
          </div>
          <div className="risk-gauge-bar">
            <div className={`risk-gauge-fill ${getGaugeClass(metrics.exposure.percentage)}`} style={{ width: `${metrics.exposure.percentage}%` }} />
          </div>
          <div className="risk-gauge-markers">
            <span>{formatCurrency(metrics.exposure.current)}</span>
            <span>{formatCurrency(metrics.exposure.limit)} limit</span>
          </div>
        </div>
      </div>
      
      <div className="chart-container">
        <div className="chart-header">
          <span className="chart-title">Exposure by Symbol</span>
        </div>
        {metrics.exposureBySymbol.map(item => (
          <div key={item.symbol} style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <span style={{ width: 60, fontSize: '11px', fontFamily: 'var(--font-mono)' }}>{item.symbol}</span>
            <div style={{ flex: 1, height: '12px', background: 'var(--kg-border)', borderRadius: '2px' }}>
              <div style={{ width: `${item.percentage}%`, height: '100%', background: 'var(--kg-gold)', borderRadius: '2px' }} />
            </div>
            <span style={{ width: 60, textAlign: 'right', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>{formatCurrency(item.amount)}</span>
          </div>
        ))}
      </div>
      
      <div className="risk-events">
        <div className="chart-header">
          <span className="chart-title">Risk Events Log</span>
        </div>
        {metrics.riskEvents.map((event, i) => (
          <div key={i} className="risk-event">
            <span className="risk-event-time">{formatTime(event.time)}</span>
            <span className={`alert-badge ${event.severity.toLowerCase()}`}>{event.severity}</span>
            <span className="risk-event-message">{event.message}</span>
          </div>
        ))}
      </div>
      
      <div className="emergency-section">
        <div className="emergency-header">⚠ Emergency Controls</div>
        <div className="emergency-status">
          <span className="emergency-status-label">Kill Switch:</span>
          <span className="emergency-status-value">ARMED</span>
        </div>
        <div className="emergency-status" style={{ marginTop: 8 }}>
          <span className="emergency-status-label">Trigger:</span>
          <span className="emergency-status-value">Drawdown {'>'} 10%</span>
        </div>
      </div>
    </div>
  );
};

const MarketWatchPanel = ({ prices }) => {
  const symbols = Object.keys(prices);
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">Market Watch</h1>
          <p className="panel-subtitle">Live tick data • Last update: just now</p>
        </div>
      </div>
      
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Symbol</span>
          <input type="text" className="input" placeholder="Search symbols..." style={{ width: 150 }} />
        </div>
      </div>
      
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Bid</th>
              <th>Ask</th>
              <th>Spread</th>
              <th>Daily Change</th>
              <th>Daily %</th>
              <th>High</th>
              <th>Low</th>
              <th>Volume</th>
            </tr>
          </thead>
          <tbody>
            {symbols.map(symbol => {
              const p = prices[symbol];
              const decimals = symbol === 'XAUUSD' || symbol.includes('JPY') ? 2 : 5;
              return (
                <tr key={symbol}>
                  <td className="text" style={{ fontWeight: 700, color: 'var(--kg-gold)' }}>{symbol}</td>
                  <td className={`market-price ${p.bid > 1 ? '' : ''}`}>{formatPrice(p.bid, decimals)}</td>
                  <td className="market-price">{formatPrice(p.ask, decimals)}</td>
                  <td>{p.spread}</td>
                  <td className={`market-price ${p.change >= 0 ? 'change-positive' : 'change-negative'}`}>
                    {p.change >= 0 ? '+' : ''}{formatPrice(Math.abs(p.change), decimals)}
                  </td>
                  <td className={`${p.changePercent >= 0 ? 'change-positive' : 'change-negative'}`}>
                    {p.changePercent >= 0 ? '↑' : '↓'} {formatPercent(p.changePercent)}
                  </td>
                  <td>{formatPrice(p.high, decimals)}</td>
                  <td>{formatPrice(p.low, decimals)}</td>
                  <td>{(p.volume / 1000).toFixed(0)}K</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const SystemLogsPanel = ({ logsData }) => {
  const { logs, filter, setFilter, autoScroll, setAutoScroll } = logsData;
  const logViewerRef = useRef(null);
  
  useEffect(() => {
    if (autoScroll && logViewerRef.current) {
      logViewerRef.current.scrollTop = 0;
    }
  }, [logs, autoScroll]);
  
  const levels = ['ALL', 'INFO', 'WARN', 'ERROR', 'DEBUG', 'TRADE'];
  const modules = ['ALL', 'core', 'ws', 'api', 'risk', 'strategy'];
  
  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">System Logs</h1>
          <p className="panel-subtitle">Real-time log stream</p>
        </div>
        <div className="panel-actions">
          <button className={`btn btn-sm ${autoScroll ? 'btn-primary' : ''}`} onClick={() => setAutoScroll(!autoScroll)}>
            Auto-scroll {autoScroll ? 'ON' : 'OFF'}
          </button>
          <button className="btn btn-sm">Clear</button>
          <button className="btn btn-sm">Export</button>
        </div>
      </div>
      
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Level</span>
          {levels.map(level => (
            <button 
              key={level}
              className={`btn btn-sm ${filter.level === level ? 'btn-primary' : ''}`}
              onClick={() => setFilter({ ...filter, level })}
            >
              {level}
            </button>
          ))}
        </div>
        <div className="filter-group">
          <span className="filter-label">Module</span>
          <select className="select" value={filter.module} onChange={(e) => setFilter({ ...filter, module: e.target.value })}>
            {modules.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="filter-group">
          <input 
            type="text" 
            className="input" 
            placeholder="Search logs..." 
            value={filter.search}
            onChange={(e) => setFilter({ ...filter, search: e.target.value })}
            style={{ width: 200 }}
          />
        </div>
      </div>
      
      <div className="log-viewer" ref={logViewerRef}>
        {logs.map((log, i) => (
          <div key={i} className="log-line">
            <span className="log-timestamp">[{formatTime(log.time)}]</span>
            <span className={`log-level ${log.level.toLowerCase()}`}>{log.level}</span>
            <span className="log-module">[{log.module}]</span>
            <span className="log-message">{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const SettingsPanel = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');


  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await api.get('/settings');
        setSettings(res.data);
      } catch (err) {
        console.error("Failed to load settings:", err);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await api.post('/settings', settings);
      if (res.data.success) {
        setMessage('✅ Settings saved successfully');
      } else {
        setMessage('❌ ' + (res.data.error || 'Save failed'));
      }
    } catch (err) {
      setMessage('❌ Connection error');
    } finally {
      setSaving(false);
      setTimeout(() => setMessage(''), 3000);
    }
  };

  if (loading) return <div className="panel-content">Loading settings...</div>;
  if (!settings) return <div className="panel-content">Error loading settings.</div>;

  return (
    <div className="panel-content">
      <div className="panel-header">
        <div>
          <h1 className="panel-title">System Settings</h1>
          <p className="panel-subtitle">Configure broker connection and trading parameters</p>
        </div>
        <button 
          className="btn btn-primary" 
          onClick={handleSave}
          disabled={saving}
          style={{ background: 'var(--kg-gold)', color: '#000', fontWeight: 700 }}
        >
          {saving ? 'SAVING...' : 'SAVE CONFIGURATION'}
        </button>
      </div>

      {message && (
        <div style={{ 
          padding: '10px', marginBottom: '20px', borderRadius: '4px',
          background: message.startsWith('✅') ? 'rgba(0, 232, 122, 0.1)' : 'rgba(255, 45, 78, 0.1)',
          color: message.startsWith('✅') ? '#00e87a' : '#ff2d4e',
          border: '1px solid currentColor',
          fontSize: '12px'
        }}>
          {message}
        </div>
      )}

      <div className="two-col">
        <div className="two-col-main">
          {/* Broker Section */}
          <div className="data-table-container" style={{ marginBottom: '24px', padding: '20px' }}>
            <h3 style={{ margin: '0 0 20px 0', fontSize: '14px', color: 'var(--kg-gold)' }}>Broker Connection (MT5)</h3>
            
            <div style={formStyles.row}>
              <div style={formStyles.col}>
                <label style={formStyles.label}>MT5 Account</label>
                <input 
                  className="input"
                  type="text" 
                  value={settings.pipeline?.data_provider?.config?.login || ''} 
                  onChange={(e) => setSettings({
                    ...settings,
                    pipeline: {
                      ...settings.pipeline,
                      data_provider: {
                        ...settings.pipeline.data_provider,
                        config: { ...settings.pipeline.data_provider.config, login: e.target.value }
                      }
                    }
                  })}
                />
              </div>
              <div style={formStyles.col}>
                <label style={formStyles.label}>MT5 Server</label>
                <input 
                  className="input"
                  type="text" 
                  value={settings.pipeline?.data_provider?.config?.server || ''} 
                  onChange={(e) => setSettings({
                    ...settings,
                    pipeline: {
                      ...settings.pipeline,
                      data_provider: {
                        ...settings.pipeline.data_provider,
                        config: { ...settings.pipeline.data_provider.config, server: e.target.value }
                      }
                    }
                  })}
                />
              </div>
            </div>
            
            <div style={formStyles.row}>
              <div style={formStyles.col}>
                <label style={formStyles.label}>MT5 Password</label>
                <input 
                  className="input"
                  type="password" 
                  value={settings.pipeline?.data_provider?.config?.password || ''} 
                  onChange={(e) => setSettings({
                    ...settings,
                    pipeline: {
                      ...settings.pipeline,
                      data_provider: {
                        ...settings.pipeline.data_provider,
                        config: { ...settings.pipeline.data_provider.config, password: e.target.value }
                      }
                    }
                  })}
                />
              </div>
            </div>
          </div>

          {/* Trading Parameters */}
          <div className="data-table-container" style={{ padding: '20px' }}>
            <h3 style={{ margin: '0 0 20px 0', fontSize: '14px', color: 'var(--kg-gold)' }}>Strategy & Execution</h3>
            
            <div style={formStyles.row}>
              <div style={formStyles.col}>
                <label style={formStyles.label}>Trading Symbol</label>
                <input 
                  className="input"
                  type="text" 
                  value={settings.trading?.symbol || ''} 
                  onChange={(e) => setSettings({
                    ...settings,
                    trading: { ...settings.trading, symbol: e.target.value }
                  })}
                />
              </div>
              <div style={formStyles.col}>
                <label style={formStyles.label}>Lot Size</label>
                <input 
                  className="input"
                  type="number" 
                  step="0.01"
                  value={settings.trading?.lot_size || 0} 
                  onChange={(e) => setSettings({
                    ...settings,
                    trading: { ...settings.trading, lot_size: parseFloat(e.target.value) }
                  })}
                />
              </div>
            </div>

            <div style={formStyles.row}>
              <div style={formStyles.col}>
                <label style={formStyles.label}>Risk Percent per Trade</label>
                <input 
                  className="input"
                  type="number" 
                  step="0.1"
                  value={settings.trading?.risk_percent || 0} 
                  onChange={(e) => setSettings({
                    ...settings,
                    trading: { ...settings.trading, risk_percent: parseFloat(e.target.value) }
                  })}
                />
              </div>
              <div style={formStyles.col}>
                <label style={formStyles.label}>Min Confluence Score</label>
                <input 
                  className="input"
                  type="number" 
                  step="0.5"
                  value={settings.confluence?.min_score || 0} 
                  onChange={(e) => setSettings({
                    ...settings,
                    confluence: { ...settings.confluence, min_score: parseFloat(e.target.value) }
                  })}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="two-col-side">
          <div className="data-table-container" style={{ padding: '20px' }}>
            <h3 style={{ margin: '0 0 20px 0', fontSize: '14px', color: 'var(--kg-gold)' }}>Active Filters</h3>
            {Object.keys(settings.layers || {}).map(layer => (
              <div key={layer} style={{ 
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 0', borderBottom: '1px solid #1a1a1a'
              }}>
                <span style={{ fontSize: '11px' }}>{layer.replace('Layer', '')}</span>
                <div 
                  className={`toggle ${settings.layers[layer] ? 'active' : ''}`}
                  onClick={() => setSettings({
                    ...settings,
                    layers: { ...settings.layers, [layer]: !settings.layers[layer] }
                  })}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const formStyles = {
  row: { display: 'flex', gap: '20px', marginBottom: '15px' },
  col: { flex: 1 },
  label: { display: 'block', fontSize: '10px', color: '#556', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '1px' }
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function KingInDashboard({ onLogout }) {
  const appState = useAppState();
  const { engineState, connected } = useEngineState();
  const accountStats = useAccountStats(engineState, connected);
  const { positions, totalPnl } = usePositions(engineState, connected);
  const strategies = useStrategies();
  const { prices } = useMarketPrices();
  const riskMetrics = useRiskMetrics();
  const logsData = useSystemLogs();
  const [brokerTime, setBrokerTime] = useState(new Date());
  
  useEffect(() => {
    const interval = setInterval(() => setBrokerTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);
  
  const panels = {
    overview: <OverviewPanel accountStats={accountStats} positions={positions} totalPnl={totalPnl} engineState={engineState} />,
    positions: <PositionsPanel positions={positions} />,
    'trade-history': <TradeHistoryPanel />,
    'strategy-engine': <StrategyEnginePanel strategies={strategies} />,
    'risk-monitor': <RiskMonitorPanel metrics={riskMetrics} />,
    'market-watch': <MarketWatchPanel prices={prices} />,
    'system-logs': <SystemLogsPanel logsData={logsData} />,
    settings: <SettingsPanel />,
  };
  
  const sidebarItems = [
    { id: 'overview', icon: '▦', label: 'Overview' },
    { id: 'positions', icon: '☰', label: 'Positions' },
    { id: 'trade-history', icon: '◷', label: 'History' },
    { id: 'strategy-engine', icon: '⚙', label: 'Strategy' },
    { id: 'risk-monitor', icon: '⛨', label: 'Risk' },
    { id: 'market-watch', icon: '◈', label: 'Market' },
    { id: 'system-logs', icon: '▸', label: 'Logs' },
    { id: 'settings', icon: '⚡', label: 'Settings' },
  ];
  
  const runningStrategies = strategies.filter(s => s.status === 'RUNNING').length;
  const [engineLoading, setEngineLoading] = useState(false);
  const [engineMessage, setEngineMessage] = useState('');

  const _engineControlFetch = useCallback(async (path) => {
    // strip leading /api if present as axios instance already has it
    const cleanPath = path.startsWith('/api') ? path.substring(4) : path;
    return api.post(cleanPath, {});
  }, []);

  const handleEngineStart = useCallback(async () => {
    setEngineLoading(true);
    setEngineMessage('');
    try {
      const res = await _engineControlFetch('/api/engine/start');
      const data = res.data;
      setEngineMessage(data.success ? (data.message || 'Engine started') : (data.error || 'Start failed'));
    } catch (e) {
      setEngineMessage('Start request failed: ' + e.message);
    } finally {
      setEngineLoading(false);
      setTimeout(() => setEngineMessage(''), 4000);
    }
  }, [_engineControlFetch]);

  const handleEngineStop = useCallback(async () => {
    setEngineLoading(true);
    setEngineMessage('');
    try {
      const res = await _engineControlFetch('/api/engine/stop');
      const data = res.data;
      setEngineMessage(data.success ? (data.message || 'Engine stopped') : (data.error || 'Stop failed'));
    } catch (e) {
      setEngineMessage('Stop request failed: ' + e.message);
    } finally {
      setEngineLoading(false);
      setTimeout(() => setEngineMessage(''), 4000);
    }
  }, [_engineControlFetch]);

  return (
    <div className={`kingin-dashboard ${appState.sidebarExpanded ? 'sidebar-expanded' : ''}`}>
      {/* Top Bar */}
      <div className="top-bar">
        <div className="top-left">
          <span className="logo">KingIn</span>
          <span className="logo-sub">CONTROL ROOM</span>
        </div>
        
        <div className="top-center">
          <div className={`status-badge ${connected ? (engineState?.running ? 'live' : 'connected') : 'offline'}`}>
            {connected ? (engineState?.running ? 'ENGINE LIVE' : 'API CONNECTED') : 'OFFLINE'}
          </div>
          <div className="broker-time">{brokerTime.toLocaleTimeString()}</div>
        </div>
        
        <div className="top-right">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '8px' }}>
            <button
              onClick={handleEngineStart}
              disabled={engineLoading || (engineState?.running === true)}
              style={{
                padding: '4px 10px', fontSize: '10px', fontWeight: 700,
                background: 'transparent', border: '1px solid #00e87a', borderRadius: '3px',
                color: '#00e87a', cursor: engineLoading || engineState?.running ? 'not-allowed' : 'pointer',
                opacity: engineLoading || engineState?.running ? 0.4 : 1,
                fontFamily: 'inherit', letterSpacing: '1px',
              }}
            >
              START
            </button>
            <button
              onClick={handleEngineStop}
              disabled={engineLoading || !engineState?.running}
              style={{
                padding: '4px 10px', fontSize: '10px', fontWeight: 700,
                background: 'transparent', border: '1px solid #ff2d4e', borderRadius: '3px',
                color: '#ff2d4e', cursor: engineLoading || !engineState?.running ? 'not-allowed' : 'pointer',
                opacity: engineLoading || !engineState?.running ? 0.4 : 1,
                fontFamily: 'inherit', letterSpacing: '1px',
              }}
            >
              STOP
            </button>
            {engineMessage && (
              <span style={{ fontSize: '10px', color: '#ffaa00', maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {engineMessage}
              </span>
            )}
          </div>
          <div className="top-stat">
            <span className="value">{runningStrategies}/{strategies.length}</span>
          </div>
          <div className="top-stat">
            <span>Open:</span>
            <span className="value">{positions.length}</span>
          </div>
          <div className={`top-stat ${totalPnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`}>
            <span>P&L:</span>
            <span className="value">{totalPnl >= 0 ? '+' : ''}{formatCurrency(totalPnl)}</span>
          </div>
          <button className="notification-bell">
            🔔
            {appState.notificationCount > 0 && (
              <span className="notification-badge">{appState.notificationCount}</span>
            )}
          </button>
          <div className="user-menu" onClick={onLogout}>
            <div className="user-avatar">KI</div>
            <span className="user-name">Admin</span>
            <span className="user-dropdown">▼</span>
          </div>
        </div>
      </div>
      
      {/* Sidebar */}
      <div 
        className="sidebar"
        onMouseEnter={() => appState.setSidebarExpanded(true)}
        onMouseLeave={() => appState.setSidebarExpanded(false)}
      >
        <div className="sidebar-nav">
          {sidebarItems.map(item => (
            <button
              key={item.id}
              className={`sidebar-item ${appState.activePanel === item.id ? 'active' : ''}`}
              onClick={() => appState.setActivePanel(item.id)}
            >
              <span className="icon">{item.icon}</span>
              <span className="label">{item.label}</span>
            </button>
          ))}
        </div>

        {/* Master Power Section in Sidebar */}
        <div className="sidebar-footer">
          <div className="master-power-container">
            <div className="master-power-label">
              {appState.sidebarExpanded ? 'SYSTEM MASTER POWER' : 'PWR'}
            </div>
            <div className="master-power-buttons">
              <button 
                className={`power-btn start ${engineState?.running ? 'active' : ''}`}
                onClick={handleEngineStart}
                disabled={engineLoading || engineState?.running}
                title="Start Trading Engine"
              >
                ON
              </button>
              <button 
                className={`power-btn stop ${!engineState?.running ? 'active' : ''}`}
                onClick={handleEngineStop}
                disabled={engineLoading || !engineState?.running}
                title="Stop Trading Engine"
              >
                OFF
              </button>
            </div>
            {engineMessage && appState.sidebarExpanded && (
              <div className="engine-mini-msg">{engineMessage}</div>
            )}
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="main-content">
        {panels[appState.activePanel] || panels.overview}
      </div>
    </div>
  );
}
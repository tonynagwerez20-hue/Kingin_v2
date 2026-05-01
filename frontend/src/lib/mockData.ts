// Mock data for KingIn dashboard - fully realistic trading data

export interface Position {
  ticket: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  volume: number;
  openPrice: number;
  currentPrice: number;
  stopLoss: number;
  takeProfit: number;
  openTime: number;
  pnl: number;
  pnlPercent: number;
}

export interface TradeHistory {
  ticket: string;
  closeTime: number;
  symbol: string;
  direction: 'BUY' | 'SELL';
  volume: number;
  openPrice: number;
  closePrice: number;
  pnl: number;
  pnlPercent: number;
  strategy: string;
  duration: number;
}

export interface Strategy {
  id: string;
  name: string;
  status: 'RUNNING' | 'STOPPED' | 'PAUSED' | 'ERROR';
  symbol: string;
  timeframe: string;
  tradestoday: number;
  winRate: number;
  sessionPnl: number;
  lastSignal: number;
  cpuUsage: number;
  logs: string[];
}

export interface MarketPrice {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  dailyChange: number;
  dailyChangePercent: number;
  dailyHigh: number;
  dailyLow: number;
  sessionVolume: number;
  lastUpdate: number;
}

export interface RiskMetric {
  dailyLossLimit: number;
  dailyLossLimitMax: number;
  maxDrawdown: number;
  maxDrawdownLimit: number;
  marginUsage: number;
  marginUsageMax: number;
  totalExposure: number;
  totalExposureMax: number;
}

export interface SystemLog {
  timestamp: number;
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG' | 'TRADE';
  module: string;
  message: string;
}

const now = Date.now();

// Real-time positions (updating every second in UI)
export const mockPositions: Position[] = [
  {
    ticket: 'TICKET001',
    symbol: 'EURUSD',
    direction: 'BUY',
    volume: 1.0,
    openPrice: 1.08432,
    currentPrice: 1.08512,
    stopLoss: 1.08200,
    takeProfit: 1.08850,
    openTime: now - 3600000,
    pnl: 80.0,
    pnlPercent: 0.73,
  },
  {
    ticket: 'TICKET002',
    symbol: 'GBPUSD',
    direction: 'SELL',
    volume: 0.5,
    openPrice: 1.27384,
    currentPrice: 1.27291,
    stopLoss: 1.27550,
    takeProfit: 1.26900,
    openTime: now - 7200000,
    pnl: 46.5,
    pnlPercent: 0.73,
  },
  {
    ticket: 'TICKET003',
    symbol: 'XAUUSD',
    direction: 'BUY',
    volume: 0.1,
    openPrice: 2342.50,
    currentPrice: 2345.20,
    stopLoss: 2338.00,
    takeProfit: 2355.00,
    openTime: now - 1800000,
    pnl: 27.0,
    pnlPercent: 0.11,
  },
  {
    ticket: 'TICKET004',
    symbol: 'USDJPY',
    direction: 'BUY',
    volume: 0.8,
    openPrice: 149.832,
    currentPrice: 149.654,
    stopLoss: 149.200,
    takeProfit: 150.500,
    openTime: now - 5400000,
    pnl: -142.4,
    pnlPercent: -0.12,
  },
  {
    ticket: 'TICKET005',
    symbol: 'AUDUSD',
    direction: 'SELL',
    volume: 0.7,
    openPrice: 0.67890,
    currentPrice: 0.67745,
    stopLoss: 0.68100,
    takeProfit: 0.67200,
    openTime: now - 10800000,
    pnl: 101.5,
    pnlPercent: 0.21,
  },
];

// Trade history (completed trades)
export const mockTradeHistory: TradeHistory[] = Array.from({ length: 50 }, (_, i) => ({
  ticket: `HIST${String(i + 1).padStart(5, '0')}`,
  closeTime: now - (i + 1) * 3600000,
  symbol: ['EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'AUDUSD', 'NZDUSD'][Math.floor(Math.random() * 6)],
  direction: Math.random() > 0.5 ? 'BUY' : 'SELL',
  volume: Math.random() * 2 + 0.1,
  openPrice: 1.0 + Math.random() * 0.1,
  closePrice: 1.0 + Math.random() * 0.1,
  pnl: (Math.random() - 0.35) * 500,
  pnlPercent: Math.random() * 3 - 1.5,
  strategy: ['ScalpBot-v2', 'TrendFollower', 'MeanReversion', 'Grid'][Math.floor(Math.random() * 4)],
  duration: Math.floor(Math.random() * 86400000),
}));

// Active strategies
export const mockStrategies: Strategy[] = [
  {
    id: 'STRAT001',
    name: 'ScalpBot-v2',
    status: 'RUNNING',
    symbol: 'EURUSD',
    timeframe: 'M5',
    tradestoday: 12,
    winRate: 75.0,
    sessionPnl: 142.30,
    lastSignal: now - 120000,
    cpuUsage: 67,
    logs: [
      '[14:32:15] Entry triggered at 1.08432',
      '[14:32:16] SL set at 1.08200',
      '[14:32:17] TP set at 1.08850',
      '[14:32:45] Trade 75 pips in profit',
      '[14:33:12] Partial exit at 1.08632',
      '[14:33:45] Close by TP trigger',
    ],
  },
  {
    id: 'STRAT002',
    name: 'TrendFollower',
    status: 'RUNNING',
    symbol: 'GBPUSD',
    timeframe: 'H1',
    tradestoday: 4,
    winRate: 60.0,
    sessionPnl: 215.50,
    lastSignal: now - 420000,
    cpuUsage: 42,
    logs: [
      '[13:45:22] 4H trend confirmation',
      '[13:45:23] Buy signal on higher TF',
      '[14:15:33] Mid-level resistance hit',
      '[14:18:45] Partial exit 50pips gain',
    ],
  },
  {
    id: 'STRAT003',
    name: 'MeanReversion',
    status: 'PAUSED',
    symbol: 'XAUUSD',
    timeframe: 'D1',
    tradestoday: 2,
    winRate: 68.0,
    sessionPnl: -45.20,
    lastSignal: now - 7200000,
    cpuUsage: 0,
    logs: [
      '[08:30:00] Strategy paused by user',
      '[08:25:15] Previous: Sell signal on reversion',
      '[08:25:16] SL: 2355.00',
    ],
  },
  {
    id: 'STRAT004',
    name: 'Grid',
    status: 'ERROR',
    symbol: 'USDJPY',
    timeframe: 'M15',
    tradestoday: 0,
    winRate: 0,
    sessionPnl: 0,
    lastSignal: now - 3600000,
    cpuUsage: 0,
    logs: [
      '[11:22:33] ERROR: Failed to fetch market data',
      '[11:22:32] Reconnecting to broker...',
      '[11:22:00] Connection lost to MT5',
    ],
  },
];

// Market prices
export const mockMarketPrices: MarketPrice[] = [
  {
    symbol: 'EURUSD',
    bid: 1.08510,
    ask: 1.08514,
    spread: 0.4,
    dailyChange: 0.00182,
    dailyChangePercent: 0.17,
    dailyHigh: 1.08650,
    dailyLow: 1.08220,
    sessionVolume: 450000,
    lastUpdate: now,
  },
  {
    symbol: 'GBPUSD',
    bid: 1.27289,
    ask: 1.27293,
    spread: 0.4,
    dailyChange: -0.00251,
    dailyChangePercent: -0.20,
    dailyHigh: 1.27580,
    dailyLow: 1.27150,
    sessionVolume: 280000,
    lastUpdate: now,
  },
  {
    symbol: 'XAUUSD',
    bid: 2345.18,
    ask: 2345.22,
    spread: 0.4,
    dailyChange: 12.50,
    dailyChangePercent: 0.54,
    dailyHigh: 2348.70,
    dailyLow: 2328.50,
    sessionVolume: 125000,
    lastUpdate: now,
  },
  {
    symbol: 'USDJPY',
    bid: 149.652,
    ask: 149.656,
    spread: 0.4,
    dailyChange: -0.432,
    dailyChangePercent: -0.29,
    dailyHigh: 150.250,
    dailyLow: 149.200,
    sessionVolume: 380000,
    lastUpdate: now,
  },
  {
    symbol: 'AUDUSD',
    bid: 0.67743,
    ask: 0.67747,
    spread: 0.4,
    dailyChange: 0.00187,
    dailyChangePercent: 0.28,
    dailyHigh: 0.68120,
    dailyLow: 0.67200,
    sessionVolume: 210000,
    lastUpdate: now,
  },
  {
    symbol: 'NZDUSD',
    bid: 0.60124,
    ask: 0.60128,
    spread: 0.4,
    dailyChange: 0.00032,
    dailyChangePercent: 0.05,
    dailyHigh: 0.60850,
    dailyLow: 0.59850,
    sessionVolume: 95000,
    lastUpdate: now,
  },
];

// Account statistics
export const mockAccountStats = {
  balance: 24831.50,
  equity: 25102.30,
  marginUsed: 1240.00,
  marginAvailable: 23862.30,
  marginUsagePercent: 4.9,
  todayPnl: 270.80,
  todayPnlPercent: 1.10,
  totalOpenTrades: 5,
  winRate: 68.4,
};

// Risk metrics
export const mockRiskMetrics: RiskMetric = {
  dailyLossLimit: 340,
  dailyLossLimitMax: 500,
  maxDrawdown: 3.2,
  maxDrawdownLimit: 10.0,
  marginUsage: 4.9,
  marginUsageMax: 50,
  totalExposure: 12400,
  totalExposureMax: 25000,
};

// System logs - comprehensive mix
export const mockSystemLogs: SystemLog[] = Array.from({ length: 100 }, (_, i) => {
  const levels: Array<'INFO' | 'WARN' | 'ERROR' | 'DEBUG' | 'TRADE'> = ['INFO', 'WARN', 'ERROR', 'DEBUG', 'TRADE'];
  const modules = ['Engine', 'WebSocket', 'Broker', 'Strategy', 'Risk', 'API', 'Parser'];
  const tradeMessages = [
    'Entry signal triggered for EURUSD',
    'Position closed with profit',
    'Stop loss hit on GBPUSD',
    'Take profit partial at level 1',
    'Trade reversed at support',
  ];
  const generalMessages = [
    'System connected',
    'Data stream synchronized',
    'Market data lag detected (50ms)',
    'Strategy heartbeat OK',
    'MT5 broker connection stable',
    'WebSocket reconnected',
    'Risk limit warning: margin 45%',
    'Daily drawdown: 5.2%',
  ];

  const level = levels[Math.floor(Math.random() * levels.length)];
  const module = modules[Math.floor(Math.random() * modules.length)];
  const message = level === 'TRADE' 
    ? tradeMessages[Math.floor(Math.random() * tradeMessages.length)]
    : generalMessages[Math.floor(Math.random() * generalMessages.length)];

  return {
    timestamp: now - i * 30000,
    level,
    module,
    message,
  };
});

// Equity curve data (7 days)
export const mockEquityCurve = Array.from({ length: 168 }, (_, i) => ({
  time: new Date(now - (167 - i) * 3600000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  equity: 25000 + Math.sin(i / 20) * 500 + Math.random() * 300,
  balance: 24800 + Math.sin(i / 22) * 400 + Math.random() * 250,
}));

// Exposure by symbol
export const mockExposureBySymbol = [
  { symbol: 'EURUSD', exposure: 4200 },
  { symbol: 'GBPUSD', exposure: 2800 },
  { symbol: 'XAUUSD', exposure: 1900 },
  { symbol: 'USDJPY', exposure: 2200 },
  { symbol: 'AUDUSD', exposure: 1300 },
];

// P&L by symbol (historical)
export const mockPnlBySymbol = [
  { symbol: 'EURUSD', pnl: 580 },
  { symbol: 'GBPUSD', pnl: -120 },
  { symbol: 'XAUUSD', pnl: 340 },
  { symbol: 'USDJPY', pnl: 280 },
  { symbol: 'AUDUSD', pnl: 650 },
  { symbol: 'NZDUSD', pnl: -80 },
];

// Win/Loss statistics
export const mockWinLossStats = {
  wins: 34,
  losses: 16,
  breakeven: 2,
};

// P&L by day of week
export const mockPnlByDay = [
  { day: 'Mon', pnl: 180 },
  { day: 'Tue', pnl: 240 },
  { day: 'Wed', pnl: 160 },
  { day: 'Thu', pnl: 320 },
  { day: 'Fri', pnl: 280 },
  { day: 'Sat', pnl: 120 },
  { day: 'Sun', pnl: 80 },
];

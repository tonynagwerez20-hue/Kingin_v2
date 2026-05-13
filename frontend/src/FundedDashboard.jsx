// FundedDashboard.jsx - Professional Multi-Page Trading Dashboard
// Clean dark mode with account login, trading panels, and settings

import { useState, useEffect } from 'react';
import api from './api.js';
import './index.css';

// Format helpers
const fmt = (n) => (n !== null && n !== undefined) ? Number(n).toFixed(2) : '--';
const fmtPrice = (n) => (n !== null && n !== undefined) ? Number(n).toFixed(1) : '--';
const fmtTime = () => new Date().toISOString().slice(11, 19);

// =============================================================================
// ACCOUNT LOGIN COMPONENT
// =============================================================================
const AccountLogin = ({ onLogin }) => {
  const [config, setConfig] = useState({
    broker: { login: '', password: '', server: '' }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await api.post('/settings', {
        pipeline: { data_provider: { config: config.broker } }
      });
      onLogin(config);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.loginContainer}>
      <div style={styles.loginCard}>
        <h2 style={styles.loginTitle}>ACCOUNT LOGIN</h2>
        <p style={styles.loginSubtitle}>Enter your broker credentials</p>
        
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label style={styles.label}>LOGIN / ACCOUNT ID</label>
            <input
              type="text"
              value={config.broker.login}
              onChange={(e) => setConfig({...config, broker: {...config.broker, login: e.target.value}})}
              placeholder="12345678"
              style={styles.input}
            />
          </div>
          
          <div style={styles.field}>
            <label style={styles.label}>PASSWORD</label>
            <input
              type="password"
              value={config.broker.password}
              onChange={(e) => setConfig({...config, broker: {...config.broker, password: e.target.value}})}
              placeholder="••••••••"
              style={styles.input}
            />
          </div>
          
          <div style={styles.field}>
            <label style={styles.label}>SERVER</label>
            <input
              type="text"
              value={config.broker.server}
              onChange={(e) => setConfig({...config, broker: {...config.broker, server: e.target.value}})}
              placeholder="ICMarkets-Demo"
              style={styles.input}
            />
          </div>
          
          {error && <div style={styles.error}>{error}</div>}
          
          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? 'CONNECTING...' : 'CONNECT TO BROKER'}
          </button>
        </form>
      </div>
    </div>
  );
};

// =============================================================================
// TRADING PAGE COMPONENT
// =============================================================================
const TradingPage = ({ account, onLogout, online, state, engineStatus, loading, newsLayerMode: propNewsLayerMode }) => {
  const [newsLayerMode, setNewsLayerMode] = useState(propNewsLayerMode || 'NORMAL');
  
  // Sync newsLayerMode from parent when it changes
  useEffect(() => {
    if (propNewsLayerMode) setNewsLayerMode(propNewsLayerMode);
  }, [propNewsLayerMode]);
  
  // API helper
  const api = {
    post: async (path, data = {}) => {
      const res = await fetch('http://localhost:8000' + path, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      return res.json();
    }
  };
  
  // Toggle news layer mode
  const toggleNewsLayer = async () => {
    const newMode = newsLayerMode === 'NORMAL' ? 'NEWS_SCALP' : 'NORMAL';
    try {
      await api.post('/news_layer', { mode: newMode });
      setNewsLayerMode(newMode);
    } catch {}
  };
  
  const balance = state?.account_balance || 0;
  const equity = state?.account_equity || balance || 0;
  const pnl = state?.floating_pnl || 0;
  const positions = state?.positions || [];
  const lastTrade = state?.last_trade;
  
  const signal = state?.signal_action || 'WAIT';
  const entryPrice = state?.entry_price;
  const stopLoss = state?.stop_loss;
  const takeProfit = state?.take_profit;
  const lotSize = state?.lot_size;
  const rrRatio = state?.rr_ratio;
  const confluence = state?.confluence_score;
  const symbol = state?.symbol || 'XAUUSD';
  const currentPrice = state?.current_price;
  const bias = state?.bias || 'NEUTRAL';
  const killzone = state?.killzone || 'N/A';
  const session = state?.session_time || 'N/A';
  const layers = state?.layers || [];
  const logs = state?.pipeline_log || [];
  const bufferStatus = state?.buffers || {};
  
  const handleStart = async () => {
    setLoading(true);
    try { await api.post('/engine/start'); } catch {}
    setTimeout(() => setLoading(false), 2000);
  };
  
  const handleStop = async () => {
    setLoading(true);
    try { await api.post('/engine/stop'); } catch {}
    setTimeout(() => setLoading(false), 2000);
  };
  
  const getSignalColor = (action) => {
    if (action === 'BUY' || action === 'LONG') return '#22c55e';
    if (action === 'SELL' || action === 'SHORT') return '#ef4444';
    return '#64748b';
  };
  
  const getPnLColor = (v) => {
    if (v > 0) return '#22c55e';
    if (v < 0) return '#ef4444';
    return '#64748b';
  };
  
  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>KINGIN</span>
          <span style={styles.tag}>PROP TRADER</span>
        </div>
        
        <div style={styles.headerCenter}>
          <span style={styles.symbol}>{symbol}</span>
          <span style={{...styles.price, color: getSignalColor(bias === 'BULLISH' ? 'BUY' : bias === 'BEARISH' ? 'SELL' : 'WAIT')}}>
            ${fmtPrice(currentPrice)}
          </span>
          <span style={{...styles.bias, background: getSignalColor(bias) + '20', color: getSignalColor(bias)}}>
            {bias}
          </span>
          <span style={{...styles.status, background: online ? '#22c55e20' : '#ef444420', color: online ? '#22c55e' : '#ef4444'}}>
            {online ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
        
        <div style={styles.headerRight}>
          <span style={styles.time}>{fmtTime()} UTC</span>
          {/* Buffer Status */}
          {bufferStatus && (
            <div style={styles.bufferStatus}>
              <span style={styles.bufferItem}>H1: {bufferStatus.H1 || 0}</span>
              <span style={styles.bufferItem}>M15: {bufferStatus.M15 || 0}</span>
              <span style={styles.bufferItem}>M5: {bufferStatus.M5 || 0}</span>
            </div>
          )}
          {/* Heartbeats */}
          {engineStatus && (
            <div style={styles.heartbeats}>
              <span style={styles.heartbeat}>
                MT5: {engineStatus.mt5?.connected ? '🟢' : '🔴'}
              </span>
              <span style={styles.heartbeat}>
                EA: {engineStatus.ea?.running ? '🟢' : '🔴'}
              </span>
            </div>
          )}
          <button onClick={onLogout} style={styles.logoutBtn}>Logout</button>
        </div>
      </header>
      
      <div style={styles.statsBar}>
        <div style={styles.statItem}>
          <span style={styles.statLabel}>ACCOUNT BALANCE</span>
          <span style={styles.statValue}>${fmt(balance)}</span>
        </div>
        <div style={styles.statItem}>
          <span style={styles.statLabel}>EQUITY</span>
          <span style={styles.statValue}>${fmt(equity)}</span>
        </div>
        <div style={styles.statItem}>
          <span style={styles.statLabel}>FLOATING P&L</span>
          <span style={{...styles.statValue, color: getPnLColor(pnl)}}>{pnl >= 0 ? '+' : ''}${fmt(pnl)}</span>
        </div>
        <div style={styles.statItem}>
          <span style={styles.statLabel}>OPEN TRADES</span>
          <span style={styles.statValue}>{positions.length}</span>
        </div>
        <div style={styles.statItem}>
          <span style={styles.statLabel}>NEWS LAYER</span>
          <button onClick={toggleNewsLayer} style={{...styles.newsLayerBtn, background: newsLayerMode === 'NORMAL' ? '#3b82f6' : '#f59e0b'}}>
            {newsLayerMode}
          </button>
        </div>
      </div>
      
      <div style={styles.mainGrid}>
        <div style={styles.col}>
          <div style={styles.panel}>
            <div style={styles.panelHeader}>MARKET BIAS</div>
            <div style={styles.panelContent}>
              <div style={styles.bigValue}>{bias}</div>
              <div style={styles.row}>
                <span style={styles.label}>Current Price</span>
                <span style={styles.value}>${fmtPrice(currentPrice)}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>Session</span>
                <span style={styles.value}>{session}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>Kill Zone</span>
                <span style={styles.value}>{killzone}</span>
              </div>
            </div>
          </div>
          
          <div style={styles.panel}>
            <div style={styles.panelHeader}>SIGNAL</div>
            <div style={styles.panelContent}>
              <div style={{...styles.bigValue, color: getSignalColor(signal)}}>{signal}</div>
              <div style={styles.row}>
                <span style={styles.label}>Entry Price</span>
                <span style={styles.value}>${entryPrice ? fmtPrice(entryPrice) : '--'}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>Stop Loss</span>
                <span style={styles.value}>${stopLoss ? fmtPrice(stopLoss) : '--'}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>Take Profit</span>
                <span style={styles.value}>${takeProfit ? fmtPrice(takeProfit) : '--'}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>RR Ratio</span>
                <span style={styles.value}>{rrRatio || '--'}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>Lot Size</span>
                <span style={styles.value}>{lotSize || '--'}</span>
              </div>
              <div style={styles.row}>
                <span style={styles.label}>Confluence</span>
                <span style={styles.value}>{confluence ? (confluence * 100).toFixed(0) + '%' : '--'}</span>
              </div>
            </div>
          </div>
          
          <div style={styles.panel}>
            <div style={styles.panelHeader}>LAST TRADE</div>
            <div style={styles.panelContent}>
              {lastTrade ? (
                <>
                  <div style={{...styles.bigValue, color: getSignalColor(lastTrade.action)}}>{lastTrade.action}</div>
                  <div style={styles.row}>
                    <span style={styles.label}>Entry</span>
                    <span style={styles.value}>${fmtPrice(lastTrade.price)}</span>
                  </div>
                  <div style={styles.row}>
                    <span style={styles.label}>SL</span>
                    <span style={styles.value}>${fmtPrice(lastTrade.sl)}</span>
                  </div>
                  <div style={styles.row}>
                    <span style={styles.label}>TP</span>
                    <span style={styles.value}>${fmtPrice(lastTrade.tp)}</span>
                  </div>
                  <div style={styles.row}>
                    <span style={styles.label}>Lots</span>
                    <span style={styles.value}>{lastTrade.lots}</span>
                  </div>
                </>
              ) : (
                <div style={styles.empty}>No trades yet</div>
              )}
            </div>
          </div>
        </div>
        
        <div style={styles.col}>
          <div style={styles.panel}>
            <div style={styles.panelHeader}>POSITIONS ({positions.length})</div>
            <div style={styles.panelContent}>
              {positions.length > 0 ? (
                positions.map((pos, i) => (
                  <div key={i} style={styles.positionRow}>
                    <span style={{...styles.dir, color: getSignalColor(pos.type)}}>{pos.type}</span>
                    <span style={styles.posSymbol}>{pos.symbol}</span>
                    <span style={styles.posLots}>{pos.lots}</span>
                    <span style={styles.posPrice}>@{fmtPrice(pos.open_price)}</span>
                    <span style={{...styles.posPnl, color: getPnLColor(pos.floating_pnl)}}>
                      {pos.floating_pnl >= 0 ? '+' : ''}${fmt(pos.floating_pnl)}
                    </span>
                  </div>
                ))
              ) : (
                <div style={styles.empty}>📊 No active positions</div>
              )}
            </div>
          </div>
          
          <div style={styles.panel}>
            <div style={styles.panelHeader}>ENGINE CONTROL</div>
            <div style={styles.panelContent}>
              <button onClick={handleStart} style={styles.engineBtn} disabled={loading}>
                Start Engine
              </button>
              <button onClick={handleStop} style={{...styles.engineBtn, background: '#ef4444'}} disabled={loading}>
                Stop Engine
              </button>
            </div>
          </div>
        </div>
        
        <div style={styles.col}>
          <div style={styles.panel}>
            <div style={styles.panelHeader}>STRATEGY LAYERS</div>
            <div style={styles.panelContent}>
              {layers.length > 0 ? layers.map((layer, i) => (
                <div key={i} style={styles.layerRow}>
                  <span style={styles.layerName}>{layer.name}</span>
                  <span style={{...styles.layerScore, color: layer.passed ? '#22c55e' : '#64748b'}}>
                    {layer.score}
                  </span>
                </div>
              )) : <div style={styles.empty}>No active layers</div>}
            </div>
          </div>
          
          <div style={styles.panel}>
            <div style={styles.panelHeader}>ACTIVITY LOG</div>
            <div style={styles.logContent}>
              {logs.map((log, i) => (
                <div key={i} style={styles.logEntry}>{log}</div>
              ))}
              {logs.length === 0 && <div style={styles.empty}>Waiting for activity...</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// SETTINGS PAGE COMPONENT  
// =============================================================================
const SettingsPage = ({ config, onSave, onBack }) => {
  const [settings, setSettings] = useState({
    newsLayer: config?.newsLayer || false,
    symbol: config?.symbol || 'XAUUSD',
    lotSize: config?.lotSize || 0.01,
    riskPercent: config?.riskPercent || 1.0
  });
  const [saving, setSaving] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    try {
      // Toggle news layer mode
      await api.post('/news_layer', {
        mode: settings.newsLayer ? 'NEWS_SCALP' : 'NORMAL'
      });
      // Also save other settings
      await api.post('/settings', {
        trading: { symbol: settings.symbol, lot_size: settings.lotSize, risk_percent: settings.riskPercent }
      });
      onSave(settings);
    } catch {}
    setSaving(false);
  };
  
  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <button onClick={onBack} style={styles.backBtn}>← Back</button>
          <span style={styles.logo}>KINGIN</span>
        </div>
      </header>
      
      <div style={styles.settingsPanel}>
        <h2 style={styles.settingsTitle}>SETTINGS</h2>
        
        <div style={styles.settingRow}>
          <label style={styles.settingLabel}>NEWS LAYER</label>
          <div style={styles.toggleRow}>
            <span style={styles.toggleDesc}>Enable news scalp mode</span>
            <button 
              onClick={() => setSettings({...settings, newsLayer: !settings.newsLayer})}
              style={{
                ...styles.toggle,
                background: settings.newsLayer ? '#22c55e' : '#334155'
              }}
            >
              <span style={{
                ...styles.toggleKnob,
                transform: settings.newsLayer ? 'translateX(20px)' : 'translateX(0)'
              }} />
            </button>
          </div>
        </div>
        
        <div style={styles.settingRow}>
          <label style={styles.settingLabel}>TRADING SYMBOL</label>
          <input 
            type="text" 
            value={settings.symbol}
            onChange={(e) => setSettings({...settings, symbol: e.target.value})}
            style={styles.settingInput}
          />
        </div>
        
        <div style={styles.settingRow}>
          <label style={styles.settingLabel}>DEFAULT LOT SIZE</label>
          <input 
            type="number" 
            step="0.01"
            value={settings.lotSize}
            onChange={(e) => setSettings({...settings, lotSize: Number(e.target.value)})}
            style={styles.settingInput}
          />
        </div>
        
        <div style={styles.settingRow}>
          <label style={styles.settingLabel}>RISK PER TRADE (%)</label>
          <input 
            type="number" 
            step="0.1"
            value={settings.riskPercent}
            onChange={(e) => setSettings({...settings, riskPercent: Number(e.target.value)})}
            style={styles.settingInput}
          />
        </div>
        
        <button onClick={handleSave} style={styles.saveBtn} disabled={saving}>
          {saving ? 'SAVING...' : 'SAVE SETTINGS'}
        </button>
      </div>
    </div>
  );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================
const FundedDashboard = ({ sessionToken, onLogout }) => {
  const [page, setPage] = useState('trading');
  const [account, setAccount] = useState(null);
  const [config, setConfig] = useState({});
  const [online, setOnline] = useState(false);
  const [state, setState] = useState(null);
  const [engineStatus, setEngineStatus] = useState(null);
  const [newsLayerMode, setNewsLayerMode] = useState('NORMAL');
  const [loading, setLoading] = useState(false);
  
  // Poll engine state and status every 2 seconds
  useEffect(() => {
    if (page !== 'trading') return;
    
    let mounted = true;
    const poll = async () => {
      try {
        // Get engine state
        const stateRes = await fetch('http://localhost:8000/engine_state');
        if (stateRes.ok) {
          const data = await stateRes.json();
          setState(data);
          setOnline(true);
          // Also get news_layer_mode from state
          if (data.news_layer_mode) setNewsLayerMode(data.news_layer_mode);
        }
        
        // Get engine status (heartbeats)
        const statusRes = await fetch('http://localhost:8000/engine/status');
        if (statusRes.ok) {
          const status = await statusRes.json();
          setEngineStatus(status);
        }
      } catch {
        setOnline(false);
      }
    };
    
    poll();
    const interval = setInterval(poll, 2000);
    return () => { mounted = false; clearInterval(interval); };
  }, [page]);
  
  const handleStartEngine = async () => {
    setLoading(true);
    try {
      await fetch('http://localhost:8000/engine/start', { method: 'POST' });
    } catch {}
    setLoading(false);
  };
  
  const handleStopEngine = async () => {
    setLoading(true);
    try {
      await fetch('http://localhost:8000/engine/stop', { method: 'POST' });
    } catch {}
    setLoading(false);
  };
  
  const handleLogin = (acc) => {
    setAccount(acc);
    setPage('trading');
  };
  
  if (page === 'login') {
    return <AccountLogin onLogin={handleLogin} />;
  }
  
  if (page === 'settings') {
    return <SettingsPage config={config} onSave={setConfig} onBack={() => setPage('trading')} />;
  }
  
  if (!account) {
    return <AccountLogin onLogin={handleLogin} />;
  }
  
  return <TradingPage account={account} onLogout={() => { setAccount(null); setPage('login'); }} online={online} state={state} engineStatus={engineStatus} onStartEngine={handleStartEngine} onStopEngine={handleStopEngine} loading={loading} newsLayerMode={newsLayerMode} />;
};

// =============================================================================
// STYLES
// =============================================================================
const styles = {
  loginContainer: {
    minHeight: '100vh',
    background: '#0a0c10',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '20px'
  },
  loginCard: {
    background: '#13171d',
    border: '1px solid #2a3140',
    borderRadius: '16px',
    padding: '40px',
    width: '100%',
    maxWidth: '400px'
  },
  loginTitle: {
    color: '#eab308',
    fontSize: '24px',
    fontWeight: '700',
    letterSpacing: '0.3em',
    marginBottom: '8px',
    textAlign: 'center'
  },
  loginSubtitle: {
    color: '#64748b',
    fontSize: '12px',
    textAlign: 'center',
    marginBottom: '32px'
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px'
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  label: {
    color: '#64748b',
    fontSize: '10px',
    fontWeight: '600',
    letterSpacing: '0.1em'
  },
  input: {
    background: '#0a0c10',
    border: '1px solid #2a3140',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#fff',
    fontSize: '14px',
    outline: 'none'
  },
  error: {
    color: '#ef4444',
    fontSize: '12px',
    textAlign: 'center'
  },
  button: {
    background: '#eab308',
    border: 'none',
    borderRadius: '8px',
    padding: '14px',
    color: '#0a0c10',
    fontSize: '14px',
    fontWeight: '700',
    letterSpacing: '0.1em',
    cursor: 'pointer',
    marginTop: '10px'
  },
  container: {
    minHeight: '100vh',
    background: '#0a0c10',
    padding: '20px'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px'
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  headerCenter: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px'
  },
  engineControls: {
    display: 'flex',
    gap: '4px'
  },
  engineBtn: {
    padding: '4px 8px',
    border: 'none',
    borderRadius: '4px',
    color: '#fff',
    fontSize: '10px',
    fontWeight: '600',
    cursor: 'pointer'
  },
  heartbeats: {
    display: 'flex',
    gap: '8px',
    fontSize: '10px'
  },
  heartbeat: {
    color: '#64748b'
  },
  bufferStatus: {
    display: 'flex',
    gap: '8px',
    fontSize: '10px'
  },
  bufferItem: {
    color: '#64748b'
  },
  newsLayerBtn: {
    padding: '4px 8px',
    border: 'none',
    borderRadius: '4px',
    color: '#fff',
    fontSize: '10px',
    fontWeight: '600',
    cursor: 'pointer'
  },
  logo: {
    color: '#eab308',
    fontSize: '20px',
    fontWeight: '700',
    letterSpacing: '0.3em'
  },
  tag: {
    color: '#64748b',
    fontSize: '10px',
    letterSpacing: '0.2em'
  },
  symbol: {
    color: '#fff',
    fontSize: '16px',
    fontWeight: '600'
  },
  price: {
    fontSize: '18px',
    fontWeight: '700',
    fontFamily: 'monospace'
  },
  bias: {
    padding: '4px 12px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: '600',
    letterSpacing: '0.1em'
  },
  status: {
    padding: '4px 12px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: '600',
    letterSpacing: '0.1em'
  },
  time: {
    color: '#64748b',
    fontSize: '12px',
    fontFamily: 'monospace'
  },
  logoutBtn: {
    background: 'transparent',
    border: '1px solid #2a3140',
    borderRadius: '6px',
    padding: '8px 16px',
    color: '#64748b',
    fontSize: '11px',
    cursor: 'pointer'
  },
  backBtn: {
    background: 'transparent',
    border: 'none',
    color: '#64748b',
    fontSize: '14px',
    cursor: 'pointer'
  },
  statsBar: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '16px',
    marginBottom: '20px'
  },
  statItem: {
    background: '#13171d',
    border: '1px solid #2a3140',
    borderRadius: '12px',
    padding: '16px'
  },
  statLabel: {
    color: '#64748b',
    fontSize: '10px',
    letterSpacing: '0.1em',
    display: 'block',
    marginBottom: '4px'
  },
  statValue: {
    color: '#fff',
    fontSize: '18px',
    fontWeight: '600',
    fontFamily: 'monospace'
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '16px'
  },
  col: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px'
  },
  panel: {
    background: '#13171d',
    border: '1px solid #2a3140',
    borderRadius: '12px',
    overflow: 'hidden'
  },
  panelHeader: {
    background: '#1a1d24',
    padding: '12px 16px',
    color: '#64748b',
    fontSize: '10px',
    fontWeight: '600',
    letterSpacing: '0.15em',
    borderBottom: '1px solid #2a3140'
  },
  panelContent: {
    padding: '16px'
  },
  bigValue: {
    color: '#fff',
    fontSize: '24px',
    fontWeight: '700',
    marginBottom: '12px'
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '6px 0',
    borderBottom: '1px solid #1a1d24'
  },
  label: {
    color: '#64748b',
    fontSize: '11px'
  },
  value: {
    color: '#fff',
    fontSize: '12px',
    fontFamily: 'monospace'
  },
  empty: {
    color: '#64748b',
    fontSize: '12px',
    textAlign: 'center',
    padding: '20px'
  },
  positionRow: {
    display: 'grid',
    gridTemplateColumns: '40px 70px 50px 80px 80px',
    gap: '8px',
    padding: '8px 0',
    borderBottom: '1px solid #1a1d24',
    fontSize: '12px'
  },
  dir: {
    fontWeight: '700'
  },
  posSymbol: {
    color: '#fff'
  },
  posLots: {
    color: '#64748b'
  },
  posPrice: {
    fontFamily: 'monospace',
    color: '#fff'
  },
  posPnl: {
    textAlign: 'right',
    fontFamily: 'monospace'
  },
  engineBtn: {
    background: '#22c55e',
    border: 'none',
    borderRadius: '8px',
    padding: '12px 20px',
    color: '#fff',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    marginRight: '8px'
  },
  layerRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #1a1d24'
  },
  layerName: {
    color: '#fff',
    fontSize: '12px'
  },
  layerScore: {
    fontSize: '12px',
    fontWeight: '600'
  },
  logContent: {
    maxHeight: '150px',
    overflowY: 'auto'
  },
  logEntry: {
    color: '#64748b',
    fontSize: '11px',
    padding: '4px 0',
    borderBottom: '1px solid #1a1d24'
  },
  settingsPanel: {
    background: '#13171d',
    border: '1px solid #2a3140',
    borderRadius: '16px',
    padding: '40px',
    maxWidth: '500px',
    margin: '40px auto'
  },
  settingsTitle: {
    color: '#eab308',
    fontSize: '20px',
    fontWeight: '700',
    letterSpacing: '0.2em',
    marginBottom: '32px'
  },
  settingRow: {
    marginBottom: '24px'
  },
  settingLabel: {
    color: '#64748b',
    fontSize: '10px',
    letterSpacing: '0.1em',
    display: 'block',
    marginBottom: '8px'
  },
  toggleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  toggleDesc: {
    color: '#fff',
    fontSize: '14px'
  },
  toggle: {
    width: '48px',
    height: '26px',
    borderRadius: '13px',
    padding: '3px',
    cursor: 'pointer',
    transition: 'background 0.2s'
  },
  toggleKnob: {
    display: 'block',
    width: '20px',
    height: '20px',
    background: '#fff',
    borderRadius: '10px',
    transition: 'transform 0.2s'
  },
  settingInput: {
    width: '100%',
    background: '#0a0c10',
    border: '1px solid #2a3140',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#fff',
    fontSize: '14px',
    outline: 'none'
  },
  saveBtn: {
    background: '#eab308',
    border: 'none',
    borderRadius: '8px',
    padding: '14px',
    color: '#0a0c10',
    fontSize: '14px',
    fontWeight: '700',
    letterSpacing: '0.1em',
    cursor: 'pointer',
    width: '100%',
    marginTop: '20px'
  }
};

export default FundedDashboard;
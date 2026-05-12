// FundedNext Style Dashboard - Professional Prop Trading Interface
// Clean dark mode with card-based layout, real-time stats, and professional aesthetic

import { useState, useEffect } from 'react';
import { invoke } from './tauri-stub.js';
import BrandLogo from './BrandLogo.jsx';

// Format helpers
const fmt = (n) => n ? Number(n).toFixed(2) : '0.00';
const fmtPrice = (n) => n ? Number(n).toFixed(1) : '0.0';
const fmtTime = (ts) => {
  if (!ts) return '--:--:--';
  const d = new Date(ts * 1000);
  return d.toISOString().slice(11, 19);
};
const fmtDate = (ts) => {
  if (!ts) return '-';
  const d = new Date(ts * 1000);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const FundedDashboard = ({ sessionToken, onLogout }) => {
  const [state, setState] = useState(null);
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Poll engine state from backend API
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        // Connect to backend server on port 8000
        const res = await fetch('http://localhost:8000/engine_state');
        if (res.ok) {
          const data = await res.json();
          setState(data);
          setOnline(true);
          setError(null);
        } else {
          setOnline(false);
        }
      } catch (e) {
        console.error('Poll error:', e);
        setOnline(false);
      }
    };
    
    poll();
    const interval = setInterval(() => { if (mounted) poll(); }, 2000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const handleStart = async () => {
    setLoading(true);
    try { await invoke('start_engine'); } catch {}
    setTimeout(() => setLoading(false), 3000);
  };

  const handleStop = async () => {
    setLoading(true);
    try { await invoke('stop_engine'); } catch {}
    setTimeout(() => setLoading(false), 3000);
  };

  // Determine signal color
  const getSignalColor = (action) => {
    if (action === 'BUY' || action === 'LONG') return 'var(--success)';
    if (action === 'SELL' || action === 'SHORT') return 'var(--danger)';
    return 'var(--muted)';
  };

  // Determine PnL color
  const getPnLColor = (val) => {
    const v = parseFloat(val);
    if (v > 0) return 'var(--success)';
    if (v < 0) return 'var(--danger)';
    return 'var(--muted)';
  };

  // Current values
  const equity = state?.account_equity || 10000;
  const balance = state?.account_balance || 10000;
  const pnl = state?.floating_pnl || 0;
  const price = state?.current_price || 0;
  const bias = state?.bias || 'NEUTRAL';
  const signal = state?.signal_action || 'WAIT';
  const positions = state?.positions || [];
  const lastTrade = state?.last_trade || null;

  // Stats
  const maxDrawdown = 0; // Would calculated from history
  const profitTarget = 2000; // Target for challenge
  const daysPassed = 12; // Days in challenge

  return (
    <div style={styles.container}>
      {/* Header Bar */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <BrandLogo size={32} />
          <div>
            <h1 style={styles.logoText}>KingIn</h1>
            <span style={styles.headerTagline}>PROP TRADER</span>
          </div>
        </div>

        <div style={styles.headerCenter}>
          <div style={styles.pairDisplay}>
            <span style={styles.pairName}>{state?.symbol || 'XAUUSD'}</span>
            <span style={styles.pairPrice}>${fmtPrice(price)}</span>
          </div>
          <div style={styles.biasPill}>
            <span style={{
              ...styles.biasText,
              color: bias === 'BULLISH' ? 'var(--success)' : bias === 'BEARISH' ? 'var(--danger)' : 'var(--muted)'
            }}>{bias}</span>
          </div>
        </div>

        <div style={styles.headerRight}>
          <div style={{
            ...styles.statusBadge,
            background: online ? 'var(--success-bg)' : 'var(--danger-bg)'
          }}>
            <span style={{
              ...styles.statusDot,
              background: online ? 'var(--success)' : 'var(--danger)'
            }} />
            <span style={styles.statusText}>{online ? 'LIVE' : 'OFFLINE'}</span>
          </div>
          <div style={styles.clock}>
            {new Date().toISOString().slice(11, 19)} UTC
          </div>
          <button style={styles.logoutBtn} onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>

      {/* Stats Bar */}
      <div style={styles.statsBar}>
        <div style={styles.statCard}>
          <span style={styles.statLabel}>ACCOUNT BALANCE</span>
          <span style={styles.statValue}>${fmt(balance)}</span>
        </div>
        <div style={styles.statCard}>
          <span style={styles.statLabel}>EQUITY</span>
          <span style={{...styles.statValue, color: getPnLColor(pnl)}}>${fmt(equity)}</span>
        </div>
        <div style={styles.statCard}>
          <span style={styles.statLabel}>FLOATING P&L</span>
          <span style={{...styles.statValue, color: getPnLColor(pnl)}}>
            {pnl >= 0 ? '+' : ''}{fmt(pnl)}
          </span>
        </div>
        <div style={styles.statCard}>
          <span style={styles.statLabel}>PROFIT TARGET</span>
          <span style={styles.statValue}>${fmt(profitTarget)}</span>
        </div>
        <div style={styles.statCard}>
          <span style={styles.statLabel}>DAYS ACTIVE</span>
          <span style={styles.statValue}>{daysPassed}</span>
        </div>
        <div style={styles.statCard}>
          <span style={styles.statLabel}>ACTIVE TRADES</span>
          <span style={styles.statValue}>{positions.length}</span>
        </div>
      </div>

      {/* Main Content Grid */}
      <main style={styles.mainGrid}>
        
        {/* LEFT COLUMN - Market & Signal */}
        <div style={styles.column}>
          {/* Market Bias */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h3 style={styles.cardTitle}>Market Bias</h3>
            </div>
            <div style={styles.cardBody}>
              <div style={{
                ...styles.biasBox,
                borderColor: bias === 'BULLISH' ? 'var(--success)' : bias === 'BEARISH' ? 'var(--danger)' : 'var(--border)'
              }}>
                <span style={{
                  ...styles.biasBoxText,
                  color: bias === 'BULLISH' ? 'var(--success)' : bias === 'BEARISH' ? 'var(--danger)' : 'var(--muted)'
                }}>{bias}</span>
              </div>
              <div style={styles.detailGrid}>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Current Price</span>
                  <span style={styles.detailValue}>${fmtPrice(price)}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Session</span>
                  <span style={styles.detailValue}>{state?.session_time || 'NEW YORK'}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Kill Zone</span>
                  <span style={styles.detailValue}>{state?.killzone || 'None'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Current Signal */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h3 style={styles.cardTitle}>Signal</h3>
            </div>
            <div style={styles.cardBody}>
              <div style={{
                ...styles.signalBox,
                borderColor: getSignalColor(signal)
              }}>
                <span style={{
                  ...styles.signalText,
                  color: getSignalColor(signal)
                }}>{signal}</span>
              </div>
              <div style={styles.detailGrid}>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Entry Price</span>
                  <span style={styles.detailValue}>${state?.entry_price ? fmtPrice(state.entry_price) : '--'}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Stop Loss</span>
                  <span style={styles.detailValue}>${state?.stop_loss ? fmtPrice(state.stop_loss) : '--'}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Take Profit</span>
                  <span style={styles.detailValue}>${state?.take_profit ? fmtPrice(state.take_profit) : '--'}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>RR Ratio</span>
                  <span style={styles.detailValue}>{state?.rr_ratio || '--'}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Lot Size</span>
                  <span style={styles.detailValue}>{state?.lot_size || '--'}</span>
                </div>
                <div style={styles.detailItem}>
                  <span style={styles.detailLabel}>Confluence</span>
                  <span style={styles.detailValue}>{state?.confluence_score || '--'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Last Trade */}
          {lastTrade && (
            <div style={styles.card}>
              <div style={styles.cardHeader}>
                <h3 style={styles.cardTitle}>Last Trade</h3>
                <span style={styles.timestamp}>{fmtDate(lastTrade.timestamp)}</span>
              </div>
              <div style={styles.cardBody}>
                <div style={styles.tradeRow}>
                  <span style={{
                    ...styles.tradeAction,
                    color: getSignalColor(lastTrade.action)
                  }}>{lastTrade.action}</span>
                  <span style={styles.tradePair}>{lastTrade.symbol}</span>
                  <span style={styles.tradePrice}>${fmtPrice(lastTrade.price)}</span>
                </div>
                <div style={styles.tradeDetails}>
                  <span>SL: ${fmtPrice(lastTrade.sl)}</span>
                  <span>TP: ${fmtPrice(lastTrade.tp)}</span>
                  <span>{lastTrade.lots} lots</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* CENTER COLUMN - Positions */}
        <div style={styles.column}>
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h3 style={styles.cardTitle}>Active Positions</h3>
              <span style={styles.positionCount}>{positions.length} open</span>
            </div>
            <div style={styles.cardBody}>
              {positions.length === 0 ? (
                <div style={styles.emptyState}>
                  <span style={styles.emptyIcon}>📊</span>
                  <span style={styles.emptyText}>No active positions</span>
                </div>
              ) : (
                <div style={styles.positionsList}>
                  {positions.map((pos, i) => (
                    <div key={i} style={styles.positionRow}>
                      <span style={{
                        ...styles.posType,
                        color: pos.type === 'LONG' ? 'var(--success)' : 'var(--danger)'
                      }}>{pos.type}</span>
                      <span style={styles.posSymbol}>{pos.symbol}</span>
                      <span style={styles.posLots}>{pos.lots}</span>
                      <span style={styles.posPrice}>${fmtPrice(pos.open_price)}</span>
                      <span style={styles.posCurrent}>${fmtPrice(pos.current_price)}</span>
                      <span style={{
                        ...styles.posPnL,
                        color: getPnLColor(pos.floating_pnl)
                      }}>${fmt(pos.floating_pnl)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Engine Controls */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h3 style={styles.cardTitle}>Engine Control</h3>
            </div>
            <div style={styles.cardBody}>
              <div style={styles.controlButtons}>
                <button 
                  style={{...styles.ctrlBtn, ...styles.btnStart}} 
                  onClick={handleStart}
                  disabled={loading}
                >
                  {loading ? 'Starting...' : 'Start Engine'}
                </button>
                <button 
                  style={{...styles.ctrlBtn, ...styles.btnStop}} 
                  onClick={handleStop}
                  disabled={loading}
                >
                  {loading ? 'Stopping...' : 'Stop Engine'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN - Layers & Logs */}
        <div style={styles.column}>
          {/* Strategy Layers */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h3 style={styles.cardTitle}>Strategy Layers</h3>
            </div>
            <div style={styles.cardBody}>
              <div style={styles.layersList}>
                {(state?.layers || []).length === 0 ? (
                  <div style={styles.emptyState}>
                    <span style={styles.emptyText}>No active layers</span>
                  </div>
                ) : (
                  state.layers.map((layer, i) => (
                    <div key={i} style={styles.layerRow}>
                      <span style={{
                        ...styles.layerDot,
                        background: layer.passed ? 'var(--success)' : 'var(--border)'
                      }} />
                      <span style={styles.layerName}>{layer.name}</span>
                      <span style={{
                        ...styles.layerScore,
                        color: layer.passed ? 'var(--success)' : 'var(--muted)'
                      }}>{layer.score}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Pipeline Log */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h3 style={styles.cardTitle}>Activity Log</h3>
            </div>
            <div style={styles.cardBody}>
              <div style={styles.logList}>
                {((state?.pipeline_log) || []).slice(-10).map((entry, i) => (
                  <div key={i} style={styles.logEntry}>
                    <span style={styles.logText}>{entry}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

// Styles - FundedNext Inspired Dark Theme
const styles = {
  container: {
    width: '100%',
    height: '100vh',
    background: 'var(--bg)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  
  // Header
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 24px',
    background: 'var(--panel)',
    borderBottom: '1px solid var(--border)',
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  logoText: {
    fontFamily: 'var(--font-display)',
    fontSize: '20px',
    fontWeight: '700',
    color: 'var(--text)',
    margin: 0,
  },
  headerTagline: {
    fontSize: '10px',
    color: 'var(--muted)',
    letterSpacing: '2px',
    fontWeight: '600',
  },
  headerCenter: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  pairDisplay: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '8px',
  },
  pairName: {
    fontFamily: 'var(--font-display)',
    fontSize: '18px',
    fontWeight: '600',
    color: 'var(--text)',
  },
  pairPrice: {
    fontFamily: 'var(--font-mono)',
    fontSize: '24px',
    fontWeight: '600',
    color: 'var(--gold)',
  },
  biasPill: {
    padding: '6px 14px',
    borderRadius: '20px',
    border: '1px solid var(--border)',
    background: 'var(--bg)',
  },
  biasText: {
    fontSize: '12px',
    fontWeight: '700',
    letterSpacing: '1px',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  statusBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 12px',
    borderRadius: '20px',
  },
  statusDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
  },
  statusText: {
    fontSize: '11px',
    fontWeight: '600',
    color: 'var(--text)',
  },
  clock: {
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    color: 'var(--muted)',
  },
  logoutBtn: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid var(--border)',
    background: 'transparent',
    color: 'var(--muted)',
    fontSize: '12px',
    fontWeight: '500',
    cursor: 'pointer',
  },

  // Stats Bar
  statsBar: {
    display: 'grid',
    gridTemplateColumns: 'repeat(6, 1fr)',
    gap: '1px',
    background: 'var(--border)',
    padding: '1px',
  },
  statCard: {
    background: 'var(--panel)',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
  },
  statLabel: {
    fontSize: '10px',
    color: 'var(--muted)',
    letterSpacing: '1px',
    fontWeight: '600',
  },
  statValue: {
    fontFamily: 'var(--font-mono)',
    fontSize: '20px',
    fontWeight: '600',
    color: 'var(--text)',
  },

  // Main Grid
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1.2fr 1fr',
    gap: '16px',
    padding: '16px 24px',
    flex: 1,
    overflow: 'auto',
  },
  column: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },

  // Card
  card: {
    background: 'var(--panel)',
    borderRadius: '12px',
    border: '1px solid var(--border)',
    overflow: 'hidden',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--bg)',
  },
  cardTitle: {
    fontSize: '12px',
    fontWeight: '600',
    color: 'var(--muted)',
    letterSpacing: '1px',
    textTransform: 'uppercase',
    margin: 0,
  },
  cardBody: {
    padding: '16px',
  },

  // Bias Box
  biasBox: {
    padding: '20px',
    borderRadius: '8px',
    border: '2px solid var(--border)',
    textAlign: 'center',
    marginBottom: '16px',
    background: 'var(--bg)',
  },
  biasBoxText: {
    fontFamily: 'var(--font-display)',
    fontSize: '28px',
    fontWeight: '700',
    letterSpacing: '2px',
  },

  // Signal Box
  signalBox: {
    padding: '16px',
    borderRadius: '8px',
    border: '2px solid var(--border)',
    textAlign: 'center',
    marginBottom: '16px',
    background: 'var(--bg)',
  },
  signalText: {
    fontFamily: 'var(--font-display)',
    fontSize: '20px',
    fontWeight: '700',
    letterSpacing: '2px',
  },

  // Detail Grid
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  detailItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  detailLabel: {
    fontSize: '10px',
    color: 'var(--muted)',
    letterSpacing: '0.5px',
  },
  detailValue: {
    fontSize: '13px',
    color: 'var(--text)',
    fontWeight: '500',
  },

  // Trade Row
  tradeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '8px',
  },
  tradeAction: {
    fontSize: '14px',
    fontWeight: '700',
    letterSpacing: '1px',
  },
  tradePair: {
    fontWeight: '600',
    color: 'var(--text)',
  },
  tradePrice: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--text)',
  },
  tradeDetails: {
    display: 'flex',
    gap: '16px',
    fontSize: '12px',
    color: 'var(--muted)',
  },

  // Position List
  positionCount: {
    fontSize: '12px',
    color: 'var(--muted)',
  },
  positionsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  positionRow: {
    display: 'grid',
    gridTemplateColumns: '60px 80px 50px 80px 80px 80px',
    alignItems: 'center',
    padding: '8px 0',
    borderBottom: '1px solid var(--border)',
    fontSize: '12px',
  },
  posType: {
    fontWeight: '700',
    fontSize: '11px',
  },
  posSymbol: {
    fontWeight: '600',
    color: 'var(--text)',
  },
  posLots: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--gold)',
  },
  posPrice: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--muted)',
  },
  posCurrent: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--text)',
  },
  posPnL: {
    fontFamily: 'var(--font-mono)',
    fontWeight: '600',
    textAlign: 'right',
  },

  // Empty State
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 20px',
    gap: '8px',
  },
  emptyIcon: {
    fontSize: '32px',
    marginBottom: '8px',
  },
  emptyText: {
    color: 'var(--muted)',
    fontSize: '13px',
  },

  // Controls
  controlButtons: {
    display: 'flex',
    gap: '12px',
  },
  ctrlBtn: {
    flex: 1,
    padding: '12px',
    borderRadius: '8px',
    border: 'none',
    fontSize: '13px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  btnStart: {
    background: 'var(--success)',
    color: '#fff',
  },
  btnStop: {
    background: 'var(--danger)',
    color: '#fff',
  },

  // Layers
  layersList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  layerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '8px',
    borderRadius: '6px',
    background: 'var(--bg)',
  },
  layerDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
  },
  layerName: {
    flex: 1,
    fontSize: '13px',
    color: 'var(--text)',
    fontWeight: '500',
  },
  layerScore: {
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    fontWeight: '600',
  },

  // Log
  logList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    maxHeight: '200px',
    overflow: 'auto',
  },
  logEntry: {
    padding: '8px',
    borderRadius: '4px',
    background: 'var(--bg)',
    fontSize: '11px',
    color: 'var(--muted)',
  },
  logText: {
    color: 'var(--gold)',
  },

  timestamp: {
    fontSize: '10px',
    color: 'var(--muted)',
  },
};

export default FundedDashboard;
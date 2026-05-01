// Dashboard.jsx - Main trading dashboard with 8 floating panels
// Memory efficient - uses plain React without external libraries

import { useState, useEffect } from 'react';
import { invoke } from './tauri-stub.js';
import BrandLogo from './BrandLogo.jsx';

// Engine state schema interface:
// timestamp, symbol, bias, current_price, signal_action, entry_price, stop_loss, take_profit,
// lot_size, execution_type, confluence_score, killzone, session_time, rr_ratio,
// layers: [{name, passed, score, reason}],
// last_trade: {action, symbol, price, sl, tp, lots, bias, execution_type, confluence_score, timestamp},
// account_equity, account_balance, floating_pnl, open_trades_count,
// positions: [{symbol, type, lots, open_price, current_price, sl, tp, floating_pnl, open_time}],
// warnings: [string],
// pipeline_log: [string]

const Dashboard = ({ sessionToken, onLogout }) => {
  const [engineState, setEngineState] = useState(null);
  const [online, setOnline] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [utcTime, setUtcTime] = useState(new Date());
  const [errorCode, setErrorCode] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [panelToggle, setPanelToggle] = useState({
    bias: true, signal: true, lastTrade: true, layers: true,
    account: true, positions: true, warnings: true, pipeline: true,
    mlFilter: true,
  });
  const [panels, setPanels] = useState({
    bias: { minimized: false },
    signal: { minimized: false },
    lastTrade: { minimized: false },
    layers: { minimized: false },
    account: { minimized: false },
    positions: { minimized: false },
    warnings: { minimized: false },
    pipeline: { minimized: false },
    mlFilter: { minimized: false },
  });

  const panelLayout = {
    bias: { gridColumn: 'span 1' },
    signal: { gridColumn: 'span 1' },
    lastTrade: { gridColumn: 'span 1' },
    layers: { gridColumn: 'span 1' },
    account: { gridColumn: 'span 2' },
    positions: { gridColumn: 'span 2' },
    warnings: { gridColumn: 'span 2' },
    pipeline: { gridColumn: 'span 2' },
  };

  // Read engine state every 2 seconds
  useEffect(() => {
    const fetchState = async () => {
      try {
        let stateJson;
        try {
          stateJson = await invoke('read_engine_state');
          setErrorCode(null);
          setErrorMessage('');
        } catch (invokeErr) {
          console.error('[Dashboard] read_engine_state invoke error:', invokeErr);
          setErrorCode('INVOKE_FAILED');
          setErrorMessage(`Backend Error: ${invokeErr?.message || invokeErr?.toString?.() || 'Unknown error'}`);
          
          // Try fallback fetch
          try {
            const response = await fetch('engine_state.json', { cache: 'no-store' });
            if (!response.ok) throw new Error('engine_state.json not found');
            stateJson = await response.text();
            setErrorCode('FALLBACK_MODE');
            setErrorMessage('Using local file fallback (Tauri bridge unavailable)');
          } catch (fetchErr) {
            console.error('[Dashboard] Fallback fetch failed:', fetchErr);
            setErrorCode('NO_STATE_FILE');
            setErrorMessage('Cannot read trading engine data. Check engine_state.json exists.');
            setOnline(false);
            return;
          }
        }

        const state = JSON.parse(stateJson);

        // Support both ISO string timestamps (engine writes ISO) and numeric epoch seconds
        let timestamp = 0;
        if (state.timestamp) {
          if (typeof state.timestamp === 'string') {
            const parsed = Date.parse(state.timestamp);
            if (!isNaN(parsed)) {
              timestamp = Math.floor(parsed / 1000);
            } else {
              timestamp = Number(state.timestamp) || 0;
            }
          } else {
            timestamp = Number(state.timestamp) || 0;
          }
        }

        const now = Math.floor(Date.now() / 1000);
        setOnline(now - timestamp <= 10);
        setEngineState(state);
      } catch (err) {
        console.error('[Dashboard] Engine state error:', err);
        setErrorCode('PARSE_ERROR');
        setErrorMessage(`Data parsing error: ${err.message}`);
        setOnline(false);
      }
    };

    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, []);

  // UTC clock
  useEffect(() => {
    const timer = setInterval(() => setUtcTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Toggle panel visibility
  const togglePanel = (panel) => {
    setPanelToggle(prev => ({ ...prev, [panel]: !prev[panel] }));
  };

  // Toggle panel minimization
  const toggleMinimize = (panel) => {
    setPanels(prev => ({
      ...prev,
      [panel]: { ...prev[panel], minimized: !prev[panel].minimized }
    }));
  };

  const handleStartEngine = async () => {
    setLoadingStatus(true);
    try {
      const result = await invoke('start_engine');
      setOnline(true);
      setErrorCode(null);
      setErrorMessage('');
      console.log('[Dashboard] Engine start result:', result);
    } catch (e) {
      console.error('[Dashboard] Start engine error:', e);
      setErrorCode('START_FAILED');
      setErrorMessage(`Failed to start engine: ${e?.message || e?.toString?.() || 'Unknown error'}`);
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleStopEngine = async () => {
    setLoadingStatus(true);
    try {
      const result = await invoke('stop_engine');
      setOnline(false);
      setErrorCode(null);
      setErrorMessage('');
      console.log('[Dashboard] Engine stop result:', result);
    } catch (e) {
      console.error('[Dashboard] Stop engine error:', e);
      setErrorCode('STOP_FAILED');
      setErrorMessage(`Failed to stop engine: ${e?.message || e?.toString?.() || 'Unknown error'}`);
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleRestartEngine = async () => {
    setLoadingStatus(true);
    await handleStopEngine();
    setTimeout(handleStartEngine, 1500);
  };

  // Get data from engine state
  const state = engineState || {};
  const layers = state.layers || [];
  const positions = state.positions || [];
  const warnings = state.warnings || [];
  const pipelineLog = state.pipeline_log || [];

  // Format helpers
  const fmt = (n, decimals = 2) => n ? Number(n).toFixed(decimals) : '0.00';
  const fmtTime = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString() : '--:--:--';

  return (
    <div style={styles.dashboard}>
      {/* Error Banner */}
      {errorCode && (
        <div style={{
          ...styles.errorBanner,
          background: errorCode === 'FALLBACK_MODE' ? 'linear-gradient(90deg, #ff8f00, #ff6f00)' :
                     errorCode === 'PARSE_ERROR' ? 'linear-gradient(90deg, #d32f2f, #b71c1c)' :
                     'linear-gradient(90deg, #c62828, #a71f1f)'
        }}>
          <div style={styles.errorContent}>
            <span style={styles.errorIcon}>⚠</span>
            <div>
              <strong style={styles.errorTitle}>{errorCode}</strong>
              <p style={styles.errorText}>{errorMessage}</p>
            </div>
          </div>
          <button 
            onClick={() => { setErrorCode(null); setErrorMessage(''); }}
            style={styles.errorClose}
          >
            ✕
          </button>
        </div>
      )}

      {/* Professional Header with Enhanced Design */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <BrandLogo size={36} />
          <div style={styles.headerText}>
            <h1 style={styles.headerTitle}>INSTITUTIONAL TRADING SYSTEM</h1>
            <p style={styles.headerSubtitle}>Professional Algorithmic Trading Platform</p>
          </div>
        </div>
        <div style={styles.headerCenter}>
          <div style={styles.priceDisplay}>
            <span style={styles.symbol}>{state.symbol || 'XAU/USD'}</span>
            <span style={styles.price}>${fmt(state.current_price)}</span>
            <div style={{
              ...styles.biasIndicator,
              background: state.bias === 'BULLISH' ? 'var(--gradient-success)' :
                         state.bias === 'BEARISH' ? 'var(--gradient-error)' :
                         'var(--gradient-warning)'
            }}>
              <span style={styles.biasText}>{state.bias || 'NEUTRAL'}</span>
            </div>
          </div>
        </div>
        <div style={styles.headerRight}>
          <div style={styles.statusSection}>
            <div style={{
              ...styles.statusBadge,
              background: online ? 'var(--success-bg)' : 'var(--error-bg)',
              borderColor: online ? 'var(--success)' : 'var(--error)'
            }}>
              <span style={{
                ...styles.statusDot,
                color: online ? 'var(--success)' : 'var(--error)'
              }}>●</span>
              <span style={styles.statusText}>{online ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <span style={styles.clock}>{utcTime.toISOString().slice(11, 19)} UTC</span>
          </div>
          <button style={{...styles.btn, ...styles.logoutBtn}} onClick={onLogout}>
            <span>LOGOUT</span>
          </button>
        </div>
      </header>

      {/* Enhanced Control Panel */}
      <div style={styles.controlPanel}>
        <div style={styles.controlLeft}>
          <div style={styles.engineStatus}>
            <span style={styles.statusLabel}>Engine Status:</span>
            <div style={{
              ...styles.statusIndicator,
              color: online ? 'var(--success)' : 'var(--error)'
            }}>
              <span style={styles.statusDot}></span>
              <span>{online ? 'RUNNING' : 'STOPPED'}</span>
            </div>
            <span style={styles.lastUpdate}>
              Last Update: {fmtTime(state.timestamp)}
            </span>
          </div>
        </div>
        <div style={styles.controlRight}>
          <button
            onClick={handleStartEngine}
            disabled={loadingStatus}
            style={{
              ...styles.btn,
              ...styles.btnSuccess,
              opacity: loadingStatus ? 0.6 : 1,
              marginRight: 'var(--spacing-sm)'
            }}
          >
            {loadingStatus ? (
              <>
                <span style={styles.loadingSpinner}></span>
                STARTING...
              </>
            ) : (
              'START ENGINE'
            )}
          </button>
          <button
            onClick={handleStopEngine}
            disabled={loadingStatus}
            style={{
              ...styles.btn,
              ...styles.btnError,
              opacity: loadingStatus ? 0.6 : 1,
              marginRight: 'var(--spacing-sm)'
            }}
          >
            {loadingStatus ? (
              <>
                <span style={styles.loadingSpinner}></span>
                STOPPING...
              </>
            ) : (
              'STOP ENGINE'
            )}
          </button>
          <button
            onClick={handleRestartEngine}
            disabled={loadingStatus}
            style={{
              ...styles.btn,
              ...styles.btnWarning,
              opacity: loadingStatus ? 0.6 : 1
            }}
          >
            RESTART
          </button>
        </div>
      </div>

      {/* Main Dashboard Grid */}
      <div style={styles.dashboardGrid}>
        {/* Market Analysis Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Market Analysis</h2>
          <div style={styles.sectionGrid}>
            {/* Market Bias */}
            {panelToggle.bias && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Market Bias</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('bias')}>
                    {panels.bias.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.bias.minimized && (
                  <div className="card-body">
                    <div style={{
                      ...styles.biasDisplay,
                      background: state.bias === 'BULLISH' ? 'linear-gradient(135deg, #00e87a, #00c853)' :
                                 state.bias === 'BEARISH' ? 'linear-gradient(135deg, #ff2d4e, #d32f2f)' :
                                 'linear-gradient(135deg, #ffaa00, #ff8f00)'
                    }}>
                      <span style={styles.biasText}>{state.bias || 'NEUTRAL'}</span>
                    </div>
                    <div className="data-grid">
                      <div className="data-row">
                        <span className="data-label">Killzone:</span>
                        <span className="data-value">{state.killzone || 'N/A'}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Session:</span>
                        <span className="data-value">{state.session_time || 'N/A'}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Confluence:</span>
                        <span className="data-value">{fmt(state.confluence_score)} / 7.00</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Active Signal */}
            {panelToggle.signal && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Active Signal</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('signal')}>
                    {panels.signal.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.signal.minimized && (
                  <div className="card-body">
                    <div style={{
                      ...styles.signalBadge,
                      background: state.signal_action === 'BUY' ? 'linear-gradient(135deg, #00e87a, #00c853)' :
                                 state.signal_action === 'SELL' ? 'linear-gradient(135deg, #ff2d4e, #d32f2f)' :
                                 'linear-gradient(135deg, #ffaa00, #ff8f00)'
                    }}>
                      <span style={styles.signalText}>{state.signal_action || 'WAITING'}</span>
                    </div>
                    <div className="data-grid">
                      <div className="data-row">
                        <span className="data-label">Entry:</span>
                        <span className="data-value">${fmt(state.entry_price)}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Stop Loss:</span>
                        <span className="data-value negative">${fmt(state.stop_loss)}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Take Profit:</span>
                        <span className="data-value positive">${fmt(state.take_profit)}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Lot Size:</span>
                        <span className="data-value">{fmt(state.lot_size, 3)}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Execution:</span>
                        <span className="data-value">{state.execution_type || 'MARKET'}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Risk/Reward:</span>
                        <span className="data-value">{state.rr_ratio || '0.00'}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 7-Layer Confluence */}
            {panelToggle.layers && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">7-Layer Confluence</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('layers')}>
                    {panels.layers.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.layers.minimized && (
                  <div className="card-body">
                    <div style={styles.layersGrid}>
                      {layers.map((layer, i) => (
                        <div key={i} style={styles.layerItem}>
                          <div style={{
                            ...styles.layerStatus,
                            background: layer.passed ? '#00e87a' : '#ff2d4e'
                          }}>
                            {layer.passed ? '✓' : '✗'}
                          </div>
                          <div style={styles.layerInfo}>
                            <span style={styles.layerName}>{layer.name}</span>
                            <span style={styles.layerScore}>{fmt(layer.score)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    {layers.length === 7 && layers.every(l => l.passed) && (
                      <div style={styles.allPassBadge}>
                        <span>🎯 ALL LAYERS PASSED</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Trading Activity Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Trading Activity</h2>
          <div style={styles.sectionGrid}>
            {/* Last Trade */}
            {panelToggle.lastTrade && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Last Trade Execution</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('lastTrade')}>
                    {panels.lastTrade.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.lastTrade.minimized && (
                  <div className="card-body">
                    <div className="data-grid">
                      <div className="data-row">
                        <span className="data-label">Action:</span>
                        <span className={`data-value ${state.last_trade?.action === 'BUY' ? 'positive' : 'negative'}`}>
                          {state.last_trade?.action || 'N/A'}
                        </span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Symbol:</span>
                        <span className="data-value">{state.last_trade?.symbol || 'N/A'}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Price:</span>
                        <span className="data-value">${fmt(state.last_trade?.price)}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Lots:</span>
                        <span className="data-value">{fmt(state.last_trade?.lots, 3)}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Bias:</span>
                        <span className="data-value">{state.last_trade?.bias || 'N/A'}</span>
                      </div>
                      <div className="data-row">
                        <span className="data-label">Pipeline:</span>
                        <span className="data-value">ZMQBridge → HedgeEA</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Account Overview */}
            {panelToggle.account && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Account Overview</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('account')}>
                    {panels.account.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.account.minimized && (
                  <div className="card-body">
                    <div style={styles.accountMetrics}>
                      <div style={styles.metric}>
                        <span className="data-label">Equity</span>
                        <span className="data-value">
                          ${fmt(state.account_equity)}
                        </span>
                      </div>
                      <div style={styles.metric}>
                        <span className="data-label">Balance</span>
                        <span className="data-value positive">
                          ${fmt(state.account_balance)}
                        </span>
                      </div>
                      <div style={styles.metric}>
                        <span className="data-label">Floating P&L</span>
                        <span className={`data-value ${Number(state.floating_pnl) >= 0 ? 'positive' : 'negative'}`}>
                          ${fmt(state.floating_pnl)}
                        </span>
                      </div>
                      <div style={styles.metric}>
                        <span className="data-label">Open Trades</span>
                        <span style={{...styles.metricValue, color: '#ffaa00'}}>
                          {state.open_trades_count || 0}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Current Positions */}
            {panelToggle.positions && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Open Positions</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('positions')}>
                    {panels.positions.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.positions.minimized && (
                  <div className="card-body">
                    {positions.length === 0 ? (
                      <div style={styles.emptyState}>
                        <span style={styles.emptyIcon}>📊</span>
                        <span style={styles.emptyText}>No Open Positions</span>
                      </div>
                    ) : (
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Symbol</th>
                            <th>Type</th>
                            <th>Lots</th>
                            <th>Open</th>
                            <th>Current</th>
                            <th>P&L</th>
                          </tr>
                        </thead>
                        <tbody>
                          {positions.map((pos, i) => (
                            <tr key={i}>
                              <td>{pos.symbol}</td>
                              <td className={pos.type === 'BUY' ? 'positive' : 'negative'}>
                                {pos.type}
                              </td>
                              <td>{fmt(pos.lots, 3)}</td>
                              <td>{fmt(pos.open_price)}</td>
                              <td>{fmt(pos.current_price)}</td>
                              <td className={Number(pos.floating_pnl) >= 0 ? 'positive' : 'negative'}>
                                ${fmt(pos.floating_pnl)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* System Monitoring Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>System Monitoring</h2>
          <div style={styles.sectionGrid}>
            {/* Active Warnings */}
            {panelToggle.warnings && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">System Warnings</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('warnings')}>
                    {panels.warnings.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.warnings.minimized && (
                  <div className="card-body">
                    {warnings.length === 0 ? (
                      <div style={styles.emptyState}>
                        <span style={styles.emptyIcon}>✅</span>
                        <span style={styles.emptyText}>No Active Warnings</span>
                      </div>
                    ) : (
                      <div className="data-grid">
                        {warnings.map((w, i) => (
                          <div key={i} className="data-row" style={{borderBottom: '1px solid var(--border-light)'}}>
                            <span className="badge badge-warning">⚠️ Warning</span>
                            <span className="data-value" style={{flex: 1, marginLeft: 'var(--spacing-md)'}}>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Pipeline Log */}
            {panelToggle.pipeline && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Pipeline Activity</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('pipeline')}>
                    {panels.pipeline.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.pipeline.minimized && (
                  <div className="card-body">
                    <div style={styles.pipelineLog}>
                      {pipelineLog.slice(0, 15).map((entry, i) => (
                        <div key={i} className="data-row">
                          <span className="data-label" style={{minWidth: '60px'}}>
                            {new Date().toLocaleTimeString()}
                          </span>
                          <span className="data-value">{entry}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ML Filter Results */}
            {panelToggle.mlFilter && (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">🧠 ML Filter Analysis</h3>
                  <button style={styles.minimizeBtn} onClick={() => toggleMinimize('mlFilter')}>
                    {panels.mlFilter.minimized ? '+' : '−'}
                  </button>
                </div>
                {!panels.mlFilter.minimized && (
                  <div className="card-body">
                    {state.ml_filter ? (
                      <div className="data-grid">
                        <div className="data-row">
                          <span className="data-label">ML Confidence:</span>
                          <span className="data-value" style={{
                            color: state.ml_filter.confidence > 0.75 ? '#00e87a' :
                                   state.ml_filter.confidence > 0.5 ? '#ffaa00' : '#ff2d4e'
                          }}>
                            {(state.ml_filter.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="data-row">
                          <span className="data-label">Model Threshold:</span>
                          <span className="data-value">{(state.ml_filter.threshold * 100).toFixed(1)}%</span>
                        </div>
                        <div className="data-row">
                          <span className="data-label">Decision:</span>
                          <span className={`data-value ${state.ml_filter.decision === 'TRADE' ? 'positive' : 'negative'}`}>
                            {state.ml_filter.decision}
                          </span>
                        </div>
                        {state.ml_filter.features && (
                          <>
                            <div style={{gridColumn: '1/-1', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)'}}>
                              <span className="data-label">Features:</span>
                            </div>
                            <div className="data-row">
                              <span className="data-label">OB Strength:</span>
                              <span className="data-value">{(state.ml_filter.features.ob_strength * 100).toFixed(0)}%</span>
                            </div>
                            <div className="data-row">
                              <span className="data-label">FVG Present:</span>
                              <span className="data-value">{state.ml_filter.features.fvg_present ? '✓' : '✗'}</span>
                            </div>
                            <div className="data-row">
                              <span className="data-label">BOS Aligned:</span>
                              <span className="data-value">{state.ml_filter.features.bos_aligned ? '✓' : '✗'}</span>
                            </div>
                            <div className="data-row">
                              <span className="data-label">Liquidity Swept:</span>
                              <span className="data-value">{state.ml_filter.features.liquidity_swept ? '✓' : '✗'}</span>
                            </div>
                            <div className="data-row">
                              <span className="data-label">HTF Bias:</span>
                              <span className="data-value">{state.ml_filter.features.htf_bias}</span>
                            </div>
                          </>
                        )}
                      </div>
                    ) : (
                      <div style={styles.emptyState}>
                        <span style={styles.emptyIcon}>🤖</span>
                        <span style={styles.emptyText}>No ML filter data available</span>
                        <p style={{fontSize: '11px', color: '#8899aa', marginTop: '8px'}}>
                          ML data will display once the engine generates signals with ML scoring
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Panel Toggle Controls */}
      <div style={styles.panelControls}>
        <div style={styles.controlsHeader}>
          <span style={styles.controlsTitle}>Panel Controls</span>
        </div>
        <div style={styles.controlsGrid}>
          {Object.keys(panelToggle).map(panel => (
            <button
              key={panel}
              className={panelToggle[panel] ? 'btn btn-primary' : 'btn'}
              onClick={() => togglePanel(panel)}
            >
              {panel.replace(/([A-Z])/g, ' $1').trim()}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

const styles = {
  // Main Dashboard Container
  dashboard: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: 'linear-gradient(135deg, #0a0a0a 0%, #000000 100%)',
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    color: '#ffffff',
    overflow: 'hidden',
  },

  // Professional Header
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    background: 'rgba(10, 10, 10, 0.95)',
    backdropFilter: 'blur(10px)',
    borderBottom: '1px solid rgba(0, 200, 240, 0.2)',
    boxShadow: '0 2px 20px rgba(0, 0, 0, 0.3)',
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  headerText: {
    display: 'flex',
    flexDirection: 'column',
  },
  headerTitle: {
    fontFamily: "'Montserrat', sans-serif",
    fontWeight: '700',
    fontSize: '18px',
    color: '#00c8f0',
    letterSpacing: '1px',
    textTransform: 'uppercase',
    margin: 0,
  },
  headerSubtitle: {
    fontSize: '12px',
    color: '#b8ccd8',
    margin: '4px 0 0 0',
    fontWeight: '400',
  },
  headerCenter: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
  },
  priceDisplay: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 16px',
    background: 'rgba(0, 232, 122, 0.1)',
    border: '1px solid rgba(0, 232, 122, 0.3)',
    borderRadius: '8px',
  },
  symbol: {
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: '600',
    fontSize: '14px',
    color: '#ffffff',
  },
  price: {
    fontSize: '16px',
    fontWeight: '700',
    color: '#00e87a',
  },
  biasIndicator: {
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '10px',
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  statusSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  statusBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 14px',
    borderRadius: '20px',
    fontSize: '11px',
    fontWeight: '700',
    color: '#ffffff',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  statusDot: {
    fontSize: '8px',
  },
  clock: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '13px',
    color: '#b8ccd8',
    fontWeight: '500',
  },
  logoutBtn: {
    padding: '8px 16px',
    background: 'transparent',
    border: '1px solid #ff2d4e',
    borderRadius: '6px',
    color: '#ff2d4e',
    fontSize: '11px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },

  // Error Banner Styles
  errorBanner: {
    width: '100%',
    padding: '12px 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
    borderBottom: '2px solid #ff4757',
  },
  errorContent: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
    flex: 1,
  },
  errorIcon: {
    fontSize: '1.5rem',
    flexShrink: 0,
  },
  errorTitle: {
    display: 'block',
    fontWeight: '600',
    marginBottom: '4px',
  },
  errorText: {
    margin: 0,
    fontSize: '0.9rem',
    opacity: 0.9,
  },
  errorClose: {
    background: 'rgba(255, 255, 255, 0.2)',
    border: 'none',
    color: 'white',
    cursor: 'pointer',
    fontSize: '1.2rem',
    padding: '4px 12px',
    borderRadius: '4px',
    transition: 'background 0.2s',
  },

  // Control Panel
  controlPanel: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    background: 'rgba(10, 10, 10, 0.8)',
    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
  },
  controlLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
  },
  engineStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  statusLabel: {
    fontSize: '13px',
    color: '#b8ccd8',
    fontWeight: '500',
  },
  statusIndicator: {
    fontSize: '12px',
    fontWeight: '600',
    letterSpacing: '0.5px',
  },
  lastUpdate: {
    fontSize: '11px',
    color: '#8899aa',
  },
  controlRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  controlBtn: {
    padding: '10px 20px',
    borderRadius: '8px',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    border: 'none',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    transition: 'all 0.2s ease',
  },
  startBtn: {
    background: 'linear-gradient(135deg, #00e87a, #00c853)',
    color: '#000000',
    boxShadow: '0 4px 15px rgba(0, 232, 122, 0.3)',
  },
  stopBtn: {
    background: 'linear-gradient(135deg, #ff2d4e, #d32f2f)',
    color: '#ffffff',
    boxShadow: '0 4px 15px rgba(255, 45, 78, 0.3)',
  },
  restartBtn: {
    background: 'linear-gradient(135deg, #ffaa00, #ff8f00)',
    color: '#000000',
    boxShadow: '0 4px 15px rgba(255, 170, 0, 0.3)',
  },

  // Main Dashboard Grid
  dashboardGrid: {
    flex: 1,
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr',
    gap: '20px',
    padding: '20px 24px',
    overflow: 'auto',
  },

  // Section Styles
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  sectionTitle: {
    fontFamily: "'Montserrat', sans-serif",
    fontSize: '16px',
    fontWeight: '600',
    color: '#00c8f0',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    margin: 0,
    paddingBottom: '8px',
    borderBottom: '2px solid rgba(0, 200, 240, 0.3)',
  },
  sectionGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr',
    gap: '16px',
  },

  // Card Styles
  card: {
    background: 'rgba(15, 15, 15, 0.9)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '12px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    backdropFilter: 'blur(10px)',
    overflow: 'hidden',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 20px',
    background: 'rgba(0, 200, 240, 0.05)',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  },
  cardTitle: {
    fontFamily: "'Montserrat', sans-serif",
    fontSize: '14px',
    fontWeight: '600',
    color: '#ffffff',
    margin: 0,
  },
  minimizeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#8899aa',
    fontSize: '16px',
    cursor: 'pointer',
    padding: '4px',
    borderRadius: '4px',
    transition: 'all 0.2s ease',
  },
  cardBody: {
    padding: '20px',
  },

  // Market Analysis Styles
  biasDisplay: {
    padding: '20px',
    borderRadius: '8px',
    textAlign: 'center',
    marginBottom: '16px',
  },
  biasText: {
    fontFamily: "'Montserrat', sans-serif",
    fontSize: '24px',
    fontWeight: '700',
    color: '#ffffff',
    textTransform: 'uppercase',
    letterSpacing: '2px',
  },
  biasDetails: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  detailLabel: {
    fontSize: '12px',
    color: '#8899aa',
    fontWeight: '500',
  },
  detailValue: {
    fontSize: '13px',
    color: '#ffffff',
    fontWeight: '600',
  },

  signalBadge: {
    padding: '16px 24px',
    borderRadius: '8px',
    textAlign: 'center',
    marginBottom: '16px',
  },
  signalText: {
    fontFamily: "'Montserrat', sans-serif",
    fontSize: '20px',
    fontWeight: '700',
    color: '#ffffff',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
  signalDetails: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '8px',
  },
  signalRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  signalLabel: {
    fontSize: '12px',
    color: '#8899aa',
    fontWeight: '500',
  },
  signalValue: {
    fontSize: '13px',
    fontWeight: '600',
  },

  layersGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr',
    gap: '8px',
  },
  layerItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 12px',
    background: 'rgba(255, 255, 255, 0.02)',
    borderRadius: '6px',
  },
  layerStatus: {
    width: '20px',
    height: '20px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: '700',
  },
  layerInfo: {
    flex: 1,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  layerName: {
    fontSize: '13px',
    color: '#ffffff',
    fontWeight: '500',
  },
  layerScore: {
    fontSize: '12px',
    color: '#00c8f0',
    fontWeight: '600',
  },
  allPassBadge: {
    marginTop: '16px',
    padding: '12px 16px',
    background: 'linear-gradient(135deg, #00e87a, #00c853)',
    borderRadius: '8px',
    textAlign: 'center',
  },

  // Trading Activity Styles
  tradeSummary: {
    display: 'grid',
    gridTemplateColumns: '1fr',
    gap: '8px',
  },
  tradeRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tradeLabel: {
    fontSize: '12px',
    color: '#8899aa',
    fontWeight: '500',
  },
  tradeValue: {
    fontSize: '13px',
    fontWeight: '600',
  },

  accountMetrics: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  metric: {
    textAlign: 'center',
    padding: '16px',
    background: 'rgba(255, 255, 255, 0.02)',
    borderRadius: '8px',
  },
  metricLabel: {
    fontSize: '11px',
    color: '#8899aa',
    marginBottom: '8px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  metricValue: {
    fontSize: '16px',
    fontWeight: '700',
  },

  positionsTable: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  tableHeader: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr 1fr',
    gap: '8px',
    padding: '12px 0',
    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
    fontSize: '11px',
    color: '#8899aa',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  tableRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr 1fr',
    gap: '8px',
    padding: '12px 0',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
    fontSize: '12px',
  },
  symbolCell: {
    fontWeight: '600',
    color: '#ffffff',
  },
  typeCell: {
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  lotsCell: {
    color: '#00c8f0',
    fontFamily: "'JetBrains Mono', monospace",
  },
  priceCell: {
    color: '#b8ccd8',
    fontFamily: "'JetBrains Mono', monospace",
  },
  pnlCell: {
    fontWeight: '600',
    fontFamily: "'JetBrains Mono', monospace",
  },

  // System Monitoring Styles
  emptyState: {
    textAlign: 'center',
    padding: '40px 20px',
  },
  emptyIcon: {
    fontSize: '32px',
    marginBottom: '12px',
    display: 'block',
  },
  emptyText: {
    fontSize: '14px',
    color: '#8899aa',
    fontWeight: '500',
  },

  warningsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  warningItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px',
    background: 'rgba(255, 170, 0, 0.1)',
    border: '1px solid rgba(255, 170, 0, 0.2)',
    borderRadius: '6px',
  },
  warningIcon: {
    fontSize: '16px',
  },
  warningText: {
    fontSize: '13px',
    color: '#ffaa00',
    fontWeight: '500',
  },

  pipelineLog: {
    maxHeight: '300px',
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  logEntry: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '8px 12px',
    background: 'rgba(255, 255, 255, 0.02)',
    borderRadius: '4px',
    fontSize: '11px',
  },
  logTimestamp: {
    fontFamily: "'JetBrains Mono', monospace",
    color: '#8899aa',
    fontSize: '10px',
  },
  logText: {
    color: '#00c8f0',
    fontWeight: '500',
  },

  // Panel Controls
  panelControls: {
    padding: '16px 24px',
    background: 'rgba(10, 10, 10, 0.9)',
    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
  },
  controlsHeader: {
    marginBottom: '12px',
  },
  controlsTitle: {
    fontFamily: "'Montserrat', sans-serif",
    fontSize: '14px',
    fontWeight: '600',
    color: '#ffffff',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
  controlsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
    gap: '8px',
  },
  controlToggle: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    background: 'transparent',
    color: '#8899aa',
    fontSize: '11px',
    fontWeight: '500',
    cursor: 'pointer',
    textTransform: 'capitalize',
    transition: 'all 0.2s ease',
  },
};

export default Dashboard;
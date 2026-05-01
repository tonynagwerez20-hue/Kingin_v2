import React, { useState } from 'react';
import api from './api';

const SetupWizard = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [config, setConfig] = useState({
    broker: { login: '', password: '', server: '' },
    risk: { lot_size: 0.01, risk_percent: 1.0 },
    system: { symbol: 'XAUUSD' }
  });

  const handleNext = () => setStep(step + 1);
  const handleBack = () => setStep(step - 1);

  const handleFinish = async () => {
    setLoading(true);
    setError('');
    try {
      // Fetch current full config to preserve structure
      const res = await api.get('/settings');
      const fullConfig = res.data;

      // Update with wizard data
      fullConfig.pipeline.data_provider.config.login = config.broker.login;
      fullConfig.pipeline.data_provider.config.password = config.broker.password;
      fullConfig.pipeline.data_provider.config.server = config.broker.server;
      fullConfig.trading.symbol = config.system.symbol;
      fullConfig.trading.lot_size = config.risk.lot_size;
      fullConfig.trading.risk_percent = config.risk.risk_percent;

      const saveRes = await api.post('/settings', fullConfig);
      if (saveRes.data.success) {
        onComplete();
      } else {
        setError(saveRes.data.error || 'Failed to save configuration');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const containerStyle = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    height: '100vh', background: '#000', color: '#fff', fontFamily: 'Inter, sans-serif'
  };

  const cardStyle = {
    width: '400px', padding: '40px', background: '#0d0d0d', border: '1px solid #1a1a1a', borderRadius: '12px',
    boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
  };

  const titleStyle = { fontSize: '24px', fontWeight: 700, color: '#ffcc00', marginBottom: '8px' };
  const descStyle = { fontSize: '13px', color: '#888', marginBottom: '32px' };
  const labelStyle = { display: 'block', fontSize: '11px', color: '#555', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '1px' };
  const inputStyle = { width: '100%', padding: '12px', background: '#151515', border: '1px solid #222', borderRadius: '6px', color: '#fff', marginBottom: '20px', outline: 'none' };
  const btnStyle = { width: '100%', padding: '14px', background: '#ffcc00', border: 'none', borderRadius: '6px', color: '#000', fontWeight: 700, cursor: 'pointer', marginTop: '10px' };
  const skipStyle = { background: 'transparent', border: '1px solid #333', color: '#666', marginTop: '10px' };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
          {[1, 2, 3].map(s => (
            <div key={s} style={{ height: '4px', flex: 1, background: s <= step ? '#ffcc00' : '#222', borderRadius: '2px' }} />
          ))}
        </div>

        {step === 1 && (
          <div>
            <h1 style={titleStyle}>Broker Connection</h1>
            <p style={descStyle}>Connect KingIn to your MetaTrader 5 terminal.</p>
            
            <label style={labelStyle}>MT5 Account ID</label>
            <input style={inputStyle} type="text" placeholder="e.g. 298686191" value={config.broker.login} onChange={e => setConfig({...config, broker: {...config.broker, login: e.target.value}})} />
            
            <label style={labelStyle}>Server Name</label>
            <input style={inputStyle} type="text" placeholder="e.g. Exness-MT5Trial9" value={config.broker.server} onChange={e => setConfig({...config, broker: {...config.broker, server: e.target.value}})} />
            
            <label style={labelStyle}>Trading Password</label>
            <input style={inputStyle} type="password" placeholder="••••••••" value={config.broker.password} onChange={e => setConfig({...config, broker: {...config.broker, password: e.target.value}})} />
            
            <button style={btnStyle} onClick={handleNext}>NEXT STEP →</button>
          </div>
        )}

        {step === 2 && (
          <div>
            <h1 style={titleStyle}>Risk Profile</h1>
            <p style={descStyle}>Set your preferred risk parameters for the engine.</p>
            
            <label style={labelStyle}>Default Lot Size</label>
            <input style={inputStyle} type="number" step="0.01" value={config.risk.lot_size} onChange={e => setConfig({...config, risk: {...config.risk, lot_size: parseFloat(e.target.value)}})} />
            
            <label style={labelStyle}>Risk % Per Trade</label>
            <input style={inputStyle} type="number" step="0.1" value={config.risk.risk_percent} onChange={e => setConfig({...config, risk: {...config.risk, risk_percent: parseFloat(e.target.value)}})} />
            
            <div style={{ display: 'flex', gap: '10px' }}>
              <button style={{ ...btnStyle, ...skipStyle, flex: 1 }} onClick={handleBack}>BACK</button>
              <button style={{ ...btnStyle, flex: 2 }} onClick={handleNext}>CONTINUE</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h1 style={titleStyle}>System Ready</h1>
            <p style={descStyle}>Finalize your setup and launch the trading floor.</p>
            
            <label style={labelStyle}>Primary Trading Symbol</label>
            <input style={inputStyle} type="text" value={config.system.symbol} onChange={e => setConfig({...config, system: {...config.system, symbol: e.target.value}})} />
            
            {error && <p style={{ color: '#ff2d4e', fontSize: '12px', marginBottom: '15px' }}>{error}</p>}
            
            <div style={{ display: 'flex', gap: '10px' }}>
              <button style={{ ...btnStyle, ...skipStyle, flex: 1 }} onClick={handleBack}>BACK</button>
              <button style={{ ...btnStyle, flex: 2 }} onClick={handleFinish} disabled={loading}>
                {loading ? 'SAVING...' : 'FINISH & LAUNCH'}
              </button>
            </div>
          </div>
        )}
      </div>
      <p style={{ marginTop: '24px', fontSize: '11px', color: '#333' }}>© 2024 KingIn Institutional Trading • Secure Environment</p>
    </div>
  );
};

export default SetupWizard;

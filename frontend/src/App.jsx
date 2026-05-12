import React, { useState, useEffect } from 'react';
import FundedDashboard from './FundedDashboard.jsx';
import api from './api.js';
import './index.css';

const App = () => {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  // Check connection
  useEffect(() => {
    const check = async () => {
      try {
        await api.get('/system/status');
        setConnected(true);
      } catch {
        setConnected(false);
      }
      setLoading(false);
    };
    check();
  }, []);

  const handleLogout = () => {
    localStorage.clear();
    window.location.reload();
  };

  // Loading
  if (loading) {
    return (
      <div style={{
        width: '100vw',
        height: '100vh',
        background: '#0b0d10',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '24px'
      }}>
        <div style={{
          width: '48px',
          height: '48px',
          border: '3px solid rgba(234, 179, 8, 0.2)',
          borderTopColor: '#eab308',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }} />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#eab308', letterSpacing: '0.3em' }}>KINGIN</div>
          <div style={{ fontSize: '10px', color: '#64748b', marginTop: '8px', textTransform: 'uppercase', letterSpacing: '0.2em' }}>Initializing...</div>
        </div>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <FundedDashboard 
      sessionToken="demo" 
      onLogout={handleLogout} 
    />
  );
};

export default App;
// App.jsx - Main application shell
// Handles authentication state and renders Login or KingIn Dashboard

import { useState, useEffect } from 'react';
import Login from './Login.jsx';
import KingInDashboard from './KingInDashboard.jsx';
import SetupWizard from './SetupWizard.jsx';
import api from './api.js';
import './kingin.css';

const App = () => {
  const [sessionToken, setSessionToken] = useState(null);
  const [isConfigured, setIsConfigured] = useState(true);
  const [loading, setLoading] = useState(true);

  // Check session and system status on mount
  useEffect(() => {
    const checkStatus = async () => {
      // Retry up to 120 times (120s) in case backend is still booting
      const MAX_RETRIES = 120;
      let configured = true; // safe default — show login, not setup wizard
      for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
        try {
          const statusRes = await api.get('/system/status');
          configured = statusRes.data.configured ?? true;
          break; // success — exit retry loop
        } catch {
          if (attempt < MAX_RETRIES - 1) {
            await new Promise(r => setTimeout(r, 1000));
          }
        }
      }
      setIsConfigured(configured);

      // Check if already logged in
      const token = localStorage.getItem('kingin_jwt');
      if (token) setSessionToken(token);

      setLoading(false);
    };
    
    checkStatus();
  }, []);

  const handleLogin = (token) => {
    setSessionToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem('kingin_jwt');
    setSessionToken(null);
  };

  const handleSetupComplete = () => {
    setIsConfigured(true);
  };

  // Loading state
  if (loading) {
    return (
      <div style={styles.loading}>
        <div>INITIALIZING KINGIN...</div>
      </div>
    );
  }

  // First-run experience
  if (!isConfigured) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  // Render based on authentication state
  return sessionToken ? (
    <KingInDashboard sessionToken={sessionToken} onLogout={handleLogout} />
  ) : (
    <Login onLogin={handleLogin} />
  );
};

const styles = {
  loading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    background: '#000000',
    color: '#00c8f0',
    fontFamily: "'JetBrains Mono', monospace",
  },
};

export default App;
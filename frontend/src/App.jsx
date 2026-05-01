// App.jsx - Main application shell
// Handles authentication state and renders Login or KingIn Dashboard

import { useState, useEffect } from 'react';
import Login from './Login.jsx';
import KingInDashboard from './KingInDashboard.jsx';
import SetupWizard from './SetupWizard.jsx';
import RiskDisclaimer from './RiskDisclaimer.jsx';
import api from './api.js';
import './kingin.css';

const App = () => {
  const [sessionToken, setSessionToken] = useState(null);
  const [isConfigured, setIsConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [retryCount, setRetryCount] = useState(0);

  // Check if disclaimer was accepted within the last 30 days
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(() => {
    const ts = localStorage.getItem('kingin_disclaimer_ts');
    if (!ts) return false;
    return (Date.now() - parseInt(ts)) < 30 * 24 * 3600 * 1000;
  });

  useEffect(() => {
    const checkStatus = async () => {
      const MAX_RETRIES = 30;
      let configured = true;
      for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
        setRetryCount(attempt + 1);
        try {
          const statusRes = await api.get('/system/status');
          configured = statusRes.data.configured ?? true;
          break;
        } catch {
          if (attempt < MAX_RETRIES - 1) {
            await new Promise(r => setTimeout(r, 1000));
          }
        }
      }
      setIsConfigured(configured);

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
    localStorage.removeItem('kingin_ctrl');
    setSessionToken(null);
  };

  const handleSetupComplete = () => {
    setIsConfigured(true);
  };

  const handleDisclaimerAccept = () => {
    localStorage.setItem('kingin_disclaimer_ts', Date.now().toString());
    setDisclaimerAccepted(true);
  };

  const handleDisclaimerDecline = () => {
    window.close();
  };

  // Loading state
  if (loading) {
    return (
      <div style={styles.loading}>
        <div style={styles.loadingTitle}>INITIALIZING KINGIN...</div>
        <div style={styles.loadingSubtitle}>
          Connecting to API — Attempt {retryCount}/30
        </div>
        <div style={styles.loadingBar}>
          <div style={{ ...styles.loadingBarFill, width: `${(retryCount / 30) * 100}%` }} />
        </div>
      </div>
    );
  }

  // Risk disclaimer (first-time or every 30 days)
  if (!disclaimerAccepted) {
    return (
      <RiskDisclaimer
        onAccept={handleDisclaimerAccept}
        onDecline={handleDisclaimerDecline}
      />
    );
  }

  // First-run setup wizard
  if (!isConfigured) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  // Render based on authentication state
  return sessionToken ? (
    <KingInDashboard onLogout={handleLogout} />
  ) : (
    <Login onLogin={handleLogin} />
  );
};

const styles = {
  loading: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    background: '#000000',
    color: '#00c8f0',
    fontFamily: "'JetBrains Mono', monospace",
    gap: '12px',
  },
  loadingTitle: {
    fontSize: '18px',
    fontWeight: 700,
    letterSpacing: '4px',
  },
  loadingSubtitle: {
    fontSize: '11px',
    color: '#445566',
    letterSpacing: '1px',
  },
  loadingBar: {
    width: '220px',
    height: '2px',
    background: '#111',
    borderRadius: '2px',
    overflow: 'hidden',
    marginTop: '4px',
  },
  loadingBarFill: {
    height: '100%',
    background: '#00c8f0',
    borderRadius: '2px',
    transition: 'width 0.4s ease',
  },
};

export default App;
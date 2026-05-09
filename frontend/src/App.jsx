import React, { useState, useEffect } from 'react';
import MainLayout from './components/MainLayout';
import Overview from './components/panels/Overview';
import TradingPanel from './components/panels/TradingPanel';
import PortfolioPanel from './components/panels/PortfolioPanel';
import SystemPanel from './components/panels/SystemPanel';
import SettingsPanel from './components/panels/SettingsPanel';
import RiskDisclaimer from './RiskDisclaimer.jsx';
import SetupWizard from './SetupWizard.jsx';
import useStore from './store/useStore';
import api from './api.js';
import './index.css';

const App = () => {
  const { activePanel, isInitializing, setConnected, retryCount } = useStore();
  const [isConfigured, setIsConfigured] = useState(true);
  const [loading, setLoading] = useState(true);

  // Check if disclaimer was accepted
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(() => {
    const ts = localStorage.getItem('kingin_disclaimer_ts');
    if (!ts) return false;
    return (Date.now() - parseInt(ts)) < 30 * 24 * 3600 * 1000;
  });

  useEffect(() => {
    const checkStatus = async () => {
      const MAX_RETRIES = 5; // Reduced retries for faster boot, MainLayout handles persistent sync
      let configured = true;
      
      try {
        const statusRes = await api.get('/system/status');
        configured = statusRes.data.configured ?? true;
        setConnected(true);
      } catch {
        setConnected(false);
      }
      
      setIsConfigured(configured);
      setLoading(false);
    };

    checkStatus();
  }, [setConnected]);

  const handleSetupComplete = () => setIsConfigured(true);
  const handleDisclaimerAccept = () => {
    localStorage.setItem('kingin_disclaimer_ts', Date.now().toString());
    setDisclaimerAccepted(true);
  };

  const renderPanel = () => {
    switch (activePanel) {
      case 'overview': return <Overview />;
      case 'trading': return <TradingPanel />;
      case 'portfolio': return <PortfolioPanel />;
      case 'system': return <SystemPanel />;
      case 'intelligence': return <Overview />; // Placeholder
      case 'settings': return <SettingsPanel />;
      default: return <Overview />;
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="h-screen bg-kg-dark flex flex-col items-center justify-center gap-6 font-mono">
        <div className="w-16 h-16 border-4 border-kg-gold/20 border-t-kg-gold rounded-full animate-spin" />
        <div className="text-center">
          <div className="text-lg font-bold text-kg-gold tracking-[0.3em]">KINGIN SYSTEM</div>
          <div className="text-[10px] text-kg-muted mt-2 uppercase tracking-widest">Initializing Secure Environment...</div>
        </div>
      </div>
    );
  }

  // Risk disclaimer
  if (!disclaimerAccepted) {
    return (
      <RiskDisclaimer
        onAccept={handleDisclaimerAccept}
        onDecline={() => window.close()}
      />
    );
  }

  // Setup wizard
  if (!isConfigured) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  // Dashboard - NO LOGIN REQUIRED
  return (
    <MainLayout>
      {renderPanel()}
    </MainLayout>
  );
};

export default App;
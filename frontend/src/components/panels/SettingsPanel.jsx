import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Shield, Key, Server, Percent, Target, Save, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import useStore from '../../store/useStore';
import api, { setNewsToggle } from '../../api';
import NewsToggle from '../NewsToggle';

const SettingsField = ({ label, icon: Icon, type = "text", value, onChange, placeholder }) => (
  <div className="space-y-2">
    <label className="text-[10px] font-black text-kg-muted uppercase tracking-widest ml-1">{label}</label>
    <div className="relative group">
      <div className="absolute left-4 top-1/2 -translate-y-1/2 text-kg-muted group-focus-within:text-kg-gold transition-colors">
        <Icon size={18} />
      </div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-white/[0.03] border border-kg-border rounded-2xl pl-12 pr-4 py-3.5 text-sm text-white focus:border-kg-gold/50 outline-none transition-all placeholder:text-kg-muted/50"
      />
    </div>
  </div>
);

const SettingsPanel = () => {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ type: '', message: '' });
  const [config, setConfig] = useState({
    broker: { login: '', password: '', server: '' },
    risk: { lot_size: 0.01, risk_percent: 1.0 },
    system: { symbol: 'XAUUSD' },
    news: { participate: false }
  });

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await api.get('/settings');
        const data = res.data;
        setConfig({
          broker: {
            login: data.pipeline?.data_provider?.config?.login || '',
            password: data.pipeline?.data_provider?.config?.password || '',
            server: data.pipeline?.data_provider?.config?.server || ''
          },
          risk: {
            lot_size: data.trading?.lot_size || 0.01,
            risk_percent: data.trading?.risk_percent || 1.0
          },
          system: {
            symbol: data.trading?.symbol || 'XAUUSD'
          },
          news: {
            participate: data.news_participate || false
          }
        });
      } catch (err) {
        console.error('Failed to fetch settings', err);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    setStatus({ type: '', message: '' });
    try {
      const res = await api.get('/settings');
      const fullConfig = res.data;

      fullConfig.pipeline.data_provider.config.login = config.broker.login;
      fullConfig.pipeline.data_provider.config.password = config.broker.password;
      fullConfig.pipeline.data_provider.config.server = config.broker.server;
      fullConfig.trading.symbol = config.system.symbol;
      fullConfig.trading.lot_size = config.risk.lot_size;
      fullConfig.trading.risk_percent = config.risk.risk_percent;

      const saveRes = await api.post('/settings', fullConfig);
      if (saveRes.data.success) {
        setStatus({ type: 'success', message: 'Configuration updated and secured.' });
      } else {
        setStatus({ type: 'error', message: saveRes.data.error || 'Update failed.' });
      }
    } catch (err) {
      setStatus({ type: 'error', message: 'Connection failure: ' + err.message });
    } finally {
      setLoading(false);
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    }
  };

  const handleNewsToggle = async (val) => {
    try {
      const res = await setNewsToggle(val);
      if (res.data.success) {
        setConfig(prev => ({ ...prev, news: { participate: val } }));
        setStatus({ type: 'success', message: `News mode updated: ${val ? 'PARTICIPATE' : 'SIT OUT'}` });
      }
    } catch (err) {
      setStatus({ type: 'error', message: 'Failed to update news mode' });
    } finally {
      setTimeout(() => setStatus({ type: '', message: '' }), 3000);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-slide-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight uppercase">System Settings</h1>
          <p className="text-sm text-kg-muted font-medium">Configure your MT5 account and neural risk parameters.</p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleSave}
          disabled={loading}
          className="flex items-center gap-2 px-8 py-3 bg-kg-gold text-black font-black text-xs rounded-2xl shadow-lg shadow-kg-gold/20 hover:shadow-kg-gold/40 transition-all disabled:opacity-50"
        >
          {loading ? <Save className="animate-spin" size={18} /> : <Save size={18} />}
          {loading ? 'SECURING...' : 'SAVE CHANGES'}
        </motion.button>
      </div>

      {status.message && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`p-4 rounded-2xl flex items-center gap-3 border ${
            status.type === 'success' 
              ? 'bg-kg-success/10 border-kg-success/20 text-kg-success' 
              : 'bg-kg-danger/10 border-kg-danger/20 text-kg-danger'
          }`}
        >
          {status.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span className="text-xs font-bold uppercase tracking-wider">{status.message}</span>
        </motion.div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Broker Settings */}
        <div className="bg-kg-panel backdrop-blur-xl border border-kg-border rounded-[2rem] p-8 shadow-2xl relative overflow-hidden group">
          <div className="absolute -right-10 -top-10 w-32 h-32 bg-kg-gold/5 blur-3xl rounded-full" />
          <h3 className="text-sm font-black text-white flex items-center gap-3 mb-8 uppercase tracking-widest">
            <Shield size={20} className="text-kg-gold" />
            MT5 Broker Login
          </h3>
          <div className="space-y-6">
            <SettingsField 
              label="Account Number" 
              icon={Key} 
              value={config.broker.login} 
              onChange={(v) => setConfig({...config, broker: {...config.broker, login: v}})}
              placeholder="e.g. 298686191"
            />
            <SettingsField 
              label="Server Name" 
              icon={Server} 
              value={config.broker.server} 
              onChange={(v) => setConfig({...config, broker: {...config.broker, server: v}})}
              placeholder="e.g. Exness-MT5Trial9"
            />
            <SettingsField 
              label="Trading Password" 
              icon={Shield} 
              type="password"
              value={config.broker.password} 
              onChange={(v) => setConfig({...config, broker: {...config.broker, password: v}})}
              placeholder="••••••••"
            />
          </div>
        </div>

        {/* Strategy Settings */}
        <div className="space-y-8">
          <div className="bg-kg-panel backdrop-blur-xl border border-kg-border rounded-[2rem] p-8 shadow-2xl relative overflow-hidden group">
             <h3 className="text-sm font-black text-white flex items-center gap-3 mb-8 uppercase tracking-widest">
              <Target size={20} className="text-kg-gold" />
              Risk Parameters
            </h3>
            <div className="space-y-6">
              <SettingsField 
                label="Base Lot Size" 
                icon={Target} 
                type="number"
                value={config.risk.lot_size} 
                onChange={(v) => setConfig({...config, risk: {...config.risk, lot_size: parseFloat(v)}})}
              />
              <SettingsField 
                label="Risk % Per Trade" 
                icon={Percent} 
                type="number"
                value={config.risk.risk_percent} 
                onChange={(v) => setConfig({...config, risk: {...config.risk, risk_percent: parseFloat(v)}})}
              />
            </div>
          </div>

          <div className="bg-gradient-to-br from-kg-gold/10 to-transparent backdrop-blur-xl border border-kg-gold/20 rounded-[2rem] p-8 shadow-2xl relative overflow-hidden group">
             <h3 className="text-sm font-black text-white flex items-center gap-3 mb-6 uppercase tracking-widest">
              <RefreshCw size={20} className="text-kg-gold" />
              Asset Focus
            </h3>
            <SettingsField 
              label="Primary Symbol" 
              icon={Target} 
              value={config.system.symbol} 
              onChange={(v) => setConfig({...config, system: {...config.system, symbol: v.toUpperCase()}})}
            />
            <p className="mt-4 text-[10px] text-kg-muted font-medium italic">
              * The neural engine optimizes trade confluence specifically for the selected symbol.
            </p>
          </div>

          <NewsToggle 
            participate={config.news.participate} 
            onChange={handleNewsToggle}
            disabled={loading}
          />
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;

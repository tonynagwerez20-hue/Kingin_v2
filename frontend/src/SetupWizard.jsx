import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Key, Server, Target, Zap, ArrowRight, ArrowLeft, CheckCircle2, AlertCircle } from 'lucide-react';
import api from './api';

const SetupField = ({ label, icon: Icon, type = "text", value, onChange, placeholder }) => (
  <div className="space-y-2 mb-6">
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
        className="w-full bg-white/[0.03] border border-kg-border rounded-2xl pl-12 pr-4 py-4 text-sm text-white focus:border-kg-gold/50 outline-none transition-all placeholder:text-kg-muted/30"
      />
    </div>
  </div>
);

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

  return (
    <div className="min-h-screen bg-kg-dark flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-kg-gold/5 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-kg-accent/5 blur-[120px] rounded-full pointer-events-none" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-[500px] bg-kg-panel backdrop-blur-2xl border border-kg-border rounded-[2.5rem] p-10 shadow-2xl relative z-10"
      >
        <div className="flex gap-2 mb-10">
          {[1, 2, 3].map(s => (
            <div key={s} className={`h-1 flex-1 rounded-full transition-all duration-500 ${s <= step ? 'bg-kg-gold shadow-[0_0_10px_#5D5FEF]' : 'bg-white/5'}`} />
          ))}
        </div>

        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h1 className="text-2xl font-black text-white tracking-tight uppercase mb-2">Broker Credentials</h1>
              <p className="text-sm text-kg-muted mb-8">Connect the engine to your MetaTrader 5 account.</p>
              
              <SetupField label="MT5 Account ID" icon={Key} value={config.broker.login} onChange={v => setConfig({...config, broker: {...config.broker, login: v}})} placeholder="e.g. 298686191" />
              <SetupField label="Server Name" icon={Server} value={config.broker.server} onChange={v => setConfig({...config, broker: {...config.broker, server: v}})} placeholder="e.g. Exness-MT5Trial9" />
              <SetupField label="Trading Password" icon={Shield} type="password" value={config.broker.password} onChange={v => setConfig({...config, broker: {...config.broker, password: v}})} placeholder="••••••••" />
              
              <button onClick={handleNext} className="w-full py-4 bg-kg-gold text-black font-black text-xs rounded-2xl shadow-xl shadow-kg-gold/20 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2 mt-4 tracking-widest">
                NEXT STEP <ArrowRight size={16} />
              </button>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h1 className="text-2xl font-black text-white tracking-tight uppercase mb-2">Risk Strategy</h1>
              <p className="text-sm text-kg-muted mb-8">Define your neural risk parameters.</p>
              
              <SetupField label="Default Lot Size" icon={Target} type="number" value={config.risk.lot_size} onChange={v => setConfig({...config, risk: {...config.risk, lot_size: parseFloat(v)}})} />
              <SetupField label="Risk % Per Trade" icon={Zap} type="number" value={config.risk.risk_percent} onChange={v => setConfig({...config, risk: {...config.risk, risk_percent: parseFloat(v)}})} />
              
              <div className="flex gap-4 mt-8">
                <button onClick={handleBack} className="flex-1 py-4 bg-white/5 border border-white/10 text-white font-black text-xs rounded-2xl hover:bg-white/10 transition-all tracking-widest uppercase">
                  Back
                </button>
                <button onClick={handleNext} className="flex-[2] py-4 bg-kg-gold text-black font-black text-xs rounded-2xl shadow-xl shadow-kg-gold/20 hover:scale-[1.02] transition-all flex items-center justify-center gap-2 tracking-widest uppercase">
                  Continue <ArrowRight size={16} />
                </button>
              </div>
            </motion.div>
          )}

          {step === 3 && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <h1 className="text-2xl font-black text-white tracking-tight uppercase mb-2">Final Activation</h1>
              <p className="text-sm text-kg-muted mb-8">Ready to deploy the institutional trading floor.</p>
              
              <SetupField label="Primary Symbol" icon={Zap} value={config.system.symbol} onChange={v => setConfig({...config, system: {...config.system, symbol: v.toUpperCase()}})} />
              
              {error && (
                <div className="p-3 bg-kg-danger/10 border border-kg-danger/20 rounded-xl mb-6 flex items-center gap-2 text-kg-danger text-[10px] font-bold uppercase tracking-wider">
                  <AlertCircle size={14} />
                  {error}
                </div>
              )}
              
              <div className="flex gap-4 mt-8">
                <button onClick={handleBack} className="flex-1 py-4 bg-white/5 border border-white/10 text-white font-black text-xs rounded-2xl hover:bg-white/10 transition-all tracking-widest uppercase">
                  Back
                </button>
                <button 
                  onClick={handleFinish} 
                  disabled={loading}
                  className="flex-[2] py-4 bg-gradient-to-r from-kg-gold to-kg-gold-muted text-white font-black text-xs rounded-2xl shadow-xl shadow-kg-gold/20 hover:scale-[1.02] transition-all flex items-center justify-center gap-2 tracking-widest uppercase disabled:opacity-50"
                >
                  {loading ? 'DEPLOYING...' : 'FINISH & LAUNCH'}
                  {!loading && <CheckCircle2 size={16} />}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
      <p className="mt-12 text-[10px] font-bold text-kg-muted uppercase tracking-[0.3em] opacity-50">© 2024 KingIn Institutional Trading • Neural Engine v1.0</p>
    </div>
  );
};

export default SetupWizard;

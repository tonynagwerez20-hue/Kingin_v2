import React from 'react';
import { 
  Wifi, 
  WifiOff, 
  Bell, 
  User,
  Activity,
  ShieldCheck
} from 'lucide-react';
import useStore from '../store/useStore';

const StatGroup = ({ label, value, color = 'text-kg-text' }) => (
  <div className="flex flex-col items-end px-4 border-r border-kg-border last:border-0">
    <span className="text-[10px] text-kg-muted uppercase tracking-widest">{label}</span>
    <span className={`text-sm font-mono font-bold ${color}`}>{value}</span>
  </div>
);

const Header = () => {
  const { isApiReachable, isEngineRunning, account } = useStore();

  const formatCurrency = (val) => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(val);

  return (
    <header className="h-20 border-b border-kg-border/30 bg-kg-dark/20 backdrop-blur-xl flex items-center justify-between px-8 z-40 sticky top-0">
      <div className="flex items-center gap-4">
        <div className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-[10px] font-black tracking-widest transition-all ${
          isApiReachable 
            ? 'bg-kg-success/10 text-kg-success border border-kg-success/30 shadow-[0_0_15px_rgba(0,230,118,0.15)]' 
            : 'bg-kg-danger/10 text-kg-danger border border-kg-danger/30'
        }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${isApiReachable ? 'bg-kg-success animate-pulse' : 'bg-kg-danger'}`} />
          {isApiReachable ? 'API ONLINE' : 'API OFFLINE'}
        </div>

        {isApiReachable && (
          <div className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-[10px] font-black tracking-widest transition-all ${
            isEngineRunning 
              ? 'bg-kg-success/10 text-kg-success border border-kg-success/30 shadow-[0_0_15px_rgba(0,230,118,0.15)]' 
              : 'bg-kg-warning/10 text-kg-warning border border-kg-warning/30'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isEngineRunning ? 'bg-kg-success animate-pulse' : 'bg-kg-warning'}`} />
            {isEngineRunning ? 'ENGINE ACTIVE' : 'ENGINE STOPPED'}
          </div>
        )}

        <div className="flex items-center gap-2 text-kg-muted text-[10px] font-bold uppercase tracking-tighter ml-2">
          <ShieldCheck size={14} className="text-kg-gold" />
          <span>Institutional Grade</span>
        </div>
      </div>

      <div className="flex items-center">
        <div className="flex bg-white/[0.03] p-1.5 rounded-2xl border border-kg-border">
          <StatGroup 
            label="Equity" 
            value={formatCurrency(account.equity)} 
            color="text-kg-gold" 
          />
          <StatGroup 
            label="Floating P&L" 
            value={`${account.floatingPnl >= 0 ? '+' : ''}${formatCurrency(account.floatingPnl)}`}
            color={account.floatingPnl >= 0 ? 'text-kg-success' : 'text-kg-danger'}
          />
          <StatGroup 
            label="Margin" 
            value={`${account.marginPercent}%`} 
          />
        </div>
        
        <div className="flex items-center gap-4 ml-8 pl-8 border-l border-kg-border/50">
          <button className="p-2.5 text-kg-muted hover:text-white bg-white/[0.03] rounded-xl border border-kg-border hover:border-kg-gold/50 transition-all relative">
            <Bell size={18} />
            <span className="absolute top-2 right-2 w-2 h-2 bg-kg-danger rounded-full ring-4 ring-kg-dark/50"></span>
          </button>
          <div className="flex items-center gap-3 bg-gradient-to-r from-kg-gold/10 to-transparent p-1 pr-4 rounded-2xl border border-kg-gold/20 hover:border-kg-gold/50 cursor-pointer transition-all group">
            <div className="w-10 h-10 rounded-xl bg-kg-gold/20 flex items-center justify-center text-kg-gold group-hover:scale-105 transition-transform">
              <User size={20} />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-white leading-none">TRADER PRO+</span>
              <span className="text-[9px] text-kg-gold font-bold uppercase tracking-tighter">Premium Access</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;

import React from 'react';
import { motion } from 'framer-motion';
import { 
  Zap, 
  Activity, 
  Target, 
  Layers,
  AlertCircle,
  Crosshair,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import useStore from '../../store/useStore';

const SignalCard = ({ signal }) => (
  <motion.div 
    whileHover={{ x: 5 }}
    className="bg-white/[0.02] backdrop-blur-md border border-kg-border rounded-2xl p-5 hover:border-kg-gold/40 transition-all duration-300 cursor-pointer group shadow-lg"
  >
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <div className={`p-2.5 rounded-xl ${signal.side === 'BUY' ? 'bg-kg-success/10 text-kg-success border border-kg-success/20' : 'bg-kg-danger/10 text-kg-danger border border-kg-danger/20'}`}>
          {signal.side === 'BUY' ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
        </div>
        <div className="flex flex-col">
          <span className="font-black text-white tracking-wide">{signal.symbol}</span>
          <span className="text-[9px] text-kg-muted font-bold uppercase tracking-tighter">{new Date(signal.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </div>
      <div className="flex flex-col items-end">
        <span className={`text-xs font-black font-mono ${signal.score > 80 ? 'text-kg-success shadow-[0_0_10px_#00E676]' : 'text-kg-gold shadow-[0_0_10px_#5D5FEF]'}`}>
          {signal.score}%
        </span>
        <span className="text-[8px] text-kg-muted font-bold uppercase tracking-widest mt-1">Confidence</span>
      </div>
    </div>
    
    <div className="grid grid-cols-2 gap-4 mb-4">
      <div className="bg-white/[0.03] p-2 rounded-xl border border-white/[0.05]">
        <p className="text-[8px] text-kg-muted uppercase tracking-[0.2em] font-black mb-1">Target Entry</p>
        <p className="text-sm font-mono font-black text-white">{signal.price}</p>
      </div>
      <div className="bg-white/[0.03] p-2 rounded-xl border border-white/[0.05]">
        <p className="text-[8px] text-kg-muted uppercase tracking-[0.2em] font-black mb-1">Direction</p>
        <p className={`text-sm font-black ${signal.side === 'BUY' ? 'text-kg-success' : 'text-kg-danger'}`}>{signal.side}</p>
      </div>
    </div>

    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden shadow-inner">
      <motion.div 
        initial={{ width: 0 }}
        animate={{ width: `${signal.score}%` }}
        transition={{ duration: 1, ease: "easeOut" }}
        className={`h-full ${signal.side === 'BUY' ? 'bg-kg-success shadow-[0_0_10px_#00E676]' : 'bg-kg-danger shadow-[0_0_10px_#FF2A55]'}`}
      />
    </div>
  </motion.div>
);

const TradingPanel = () => {
  const { positions, signals, isEngineRunning, account, layers } = useStore();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-kg-text">Trading Terminal</h1>
          <p className="text-sm text-kg-muted">Live signals, active executions, and engine confluence.</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-kg-success/10 border border-kg-success/20 rounded-lg">
          <Activity size={14} className="text-kg-success animate-pulse" />
          <span className="text-[10px] font-bold text-kg-success uppercase tracking-widest">Market Feed Active</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-kg-panel backdrop-blur-xl border border-kg-border rounded-[2rem] overflow-hidden shadow-2xl shadow-black/30">
            <div className="p-8 border-b border-kg-border flex items-center justify-between bg-white/[0.01]">
              <h3 className="text-sm font-black text-white flex items-center gap-3 uppercase tracking-widest">
                <div className="w-2 h-2 rounded-full bg-kg-gold shadow-[0_0_8px_#5D5FEF]" />
                Active Positions
              </h3>
              <div className="flex gap-2">
                <button className="px-5 py-2 bg-kg-danger/10 text-kg-danger rounded-xl border border-kg-danger/20 text-[10px] font-black tracking-widest hover:bg-kg-danger hover:text-white transition-all shadow-lg shadow-kg-danger/10">CLOSE ALL</button>
              </div>
            </div>
            <div className="p-0 overflow-x-auto">
               <table className="w-full text-left border-collapse">
                  <thead className="text-[10px] text-kg-muted uppercase tracking-[0.2em] bg-white/[0.02]">
                    <tr>
                      <th className="px-8 py-5 font-black">Instrument</th>
                      <th className="px-8 py-5 font-black">Direction</th>
                      <th className="px-8 py-5 text-right font-black">Size</th>
                      <th className="px-8 py-5 text-right font-black">Entry</th>
                      <th className="px-8 py-5 text-right font-black">Current</th>
                      <th className="px-8 py-5 text-right font-black">SL / TP</th>
                      <th className="px-8 py-5 text-right font-black">Unrealized P&L</th>
                    </tr>
                  </thead>
                  <tbody className="text-xs divide-y divide-kg-border/50">
                    {positions.length > 0 ? positions.map((p, i) => (
                      <tr key={i} className="hover:bg-white/[0.03] transition-colors group">
                        <td className="px-8 py-5 font-black text-white group-hover:text-kg-gold transition-colors">{p.symbol}</td>
                        <td className="px-8 py-5">
                          <span className={`px-3 py-1 rounded-lg text-[10px] font-black tracking-widest ${
                            (p.type || p.direction) === 'BUY' ? 'bg-kg-success/10 text-kg-success border border-kg-success/20 shadow-[0_0_10px_rgba(0,230,118,0.1)]' : 'bg-kg-danger/10 text-kg-danger border border-kg-danger/20 shadow-[0_0_10px_rgba(255,42,85,0.1)]'
                          }`}>
                            {(p.type || p.direction)}
                          </span>
                        </td>
                        <td className="px-8 py-5 text-right font-mono font-bold text-kg-muted">{p.lots || p.volume || '--'}</td>
                        <td className="px-8 py-5 text-right font-mono font-bold text-kg-muted">{p.open_price || p.openPrice || '--'}</td>
                        <td className="px-8 py-5 text-right font-mono font-black text-white">{p.current_price || '--'}</td>
                        <td className="px-8 py-5 text-right font-mono font-bold text-kg-muted">
                           <span className="text-kg-danger/80">{p.sl || '--'}</span> <span className="mx-1 text-white/10">/</span> <span className="text-kg-success/80">{p.tp || '--'}</span>
                        </td>
                        <td className={`px-8 py-5 text-right font-mono font-black ${(p.floating_pnl || p.pnl || 0) >= 0 ? 'text-kg-success' : 'text-kg-danger'}`}>
                          {(p.floating_pnl || p.pnl || 0) >= 0 ? '+' : ''}${(p.floating_pnl || p.pnl || 0).toFixed(2)}
                        </td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan="7" className="px-8 py-20 text-center">
                          <div className="flex flex-col items-center opacity-30">
                            <Crosshair size={40} className="text-kg-muted mb-4 animate-pulse" />
                            <p className="text-kg-muted text-xs font-bold uppercase tracking-widest italic">No open trades in current session</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
               </table>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div className="bg-kg-panel border border-kg-border rounded-sm p-6">
                <h3 className="text-sm font-bold text-kg-text flex items-center gap-2 mb-4">
                  <Crosshair size={16} className="text-kg-gold" />
                  Killzone Status
                </h3>
                <div className="space-y-3">
                   <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/5">
                      <span className="text-xs text-kg-text">Current Session</span>
                      <span className={`text-[10px] font-bold uppercase ${isEngineRunning ? 'text-kg-success' : 'text-kg-muted'}`}>
                        {isEngineRunning ? (account.killzone || 'ACTIVE') : 'IDLE'}
                      </span>
                   </div>
                   <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/5 opacity-50">
                      <span className="text-xs text-kg-text">Market Regime</span>
                      <span className="text-[10px] font-bold text-kg-gold uppercase">
                        {account.regime || 'STABLE'}
                      </span>
                   </div>
                </div>
             </div>
             <div className="bg-kg-panel border border-kg-border rounded-sm p-6">
                <h3 className="text-sm font-bold text-kg-text flex items-center gap-2 mb-4">
                  <Layers size={16} className="text-kg-gold" />
                  Engine Confluence
                </h3>
                <div className="flex items-center justify-center h-20">
                   <div className="flex gap-4">
                      {(layers || []).slice(0, 3).map((layer, idx) => (
                        <div key={idx} className="flex flex-col items-center">
                           <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center font-bold text-[10px] ${layer.status ? 'border-kg-success text-kg-success' : 'border-kg-danger text-kg-danger'}`}>
                             {layer.layer ? layer.layer.split('Layer')[0].substring(0, 2).toUpperCase() : '??'}
                           </div>
                           <span className="text-[8px] text-kg-muted mt-1 uppercase">{layer.status ? 'PASS' : 'FAIL'}</span>
                        </div>
                      ))}
                      {(!layers || layers.length === 0) && (
                        <div className="text-[10px] text-kg-muted font-bold italic">No layer telemetry</div>
                      )}
                   </div>
                </div>
             </div>
          </div>
        </div>

        <div className="bg-kg-panel backdrop-blur-xl border border-kg-border rounded-[2rem] p-8 flex flex-col shadow-2xl shadow-black/30">
           <h3 className="text-sm font-black text-white flex items-center gap-3 mb-8 uppercase tracking-widest">
            <Zap size={20} className="text-kg-gold" />
            Live Signals
          </h3>
          <div className="flex-1 space-y-5 overflow-y-auto pr-2 custom-scrollbar">
             {signals && signals.length > 0 ? (
                signals.map((s, i) => <SignalCard key={i} signal={s} />)
             ) : (
               <div className="flex flex-col items-center justify-center p-12 border-2 border-white/[0.03] border-dashed rounded-3xl opacity-50 bg-white/[0.01]">
                 <Activity size={32} className="text-kg-muted mb-3 animate-pulse" />
                 <span className="text-[10px] font-bold text-kg-muted uppercase tracking-widest text-center leading-relaxed">Awaiting AI execution signals from neural engine...</span>
               </div>
             )}
          </div>
          <div className="mt-8 pt-8 border-t border-kg-border/50">
             <div className="flex items-center justify-between mb-5">
                <div className="flex flex-col">
                  <span className="text-[10px] text-white font-black uppercase tracking-widest leading-none mb-1">Neural Execution</span>
                  <span className="text-[8px] text-kg-gold font-bold uppercase tracking-tighter">Auto-Trade Enabled</span>
                </div>
                <div className="w-12 h-6 bg-kg-gold/20 rounded-full relative cursor-pointer border border-kg-gold/30">
                   <div className="absolute right-1 top-1 w-4 h-4 bg-kg-gold rounded-full shadow-[0_0_10px_#5D5FEF]" />
                </div>
             </div>
             <div className="p-4 bg-white/[0.02] border border-white/[0.05] rounded-2xl">
               <p className="text-[10px] text-kg-muted leading-relaxed font-medium">
                  {isEngineRunning 
                    ? `Automated execution is active for signals validated by ${layers?.length || 0} institutional confluence layers.`
                    : "Connect engine to enable institutional-grade automated execution."}
               </p>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingPanel;

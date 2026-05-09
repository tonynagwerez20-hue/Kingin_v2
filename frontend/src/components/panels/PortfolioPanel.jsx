import React from 'react';
import { PieChart, History, TrendingUp, ShieldAlert, Award, Target } from 'lucide-react';

const PortfolioPanel = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-kg-text">Portfolio Intelligence</h1>
          <p className="text-sm text-kg-muted">Detailed performance metrics, history, and risk analysis.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl p-6 shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
            <h3 className="text-sm font-bold text-kg-text flex items-center gap-2 mb-6">
              <Award size={16} className="text-kg-gold" />
              Success Metrics
            </h3>
            <div className="space-y-6">
               <div className="flex items-center justify-between">
                  <span className="text-xs text-kg-muted">Profit Factor</span>
                  <span className="text-sm font-mono font-bold text-kg-muted">--</span>
               </div>
               <div className="flex items-center justify-between">
                  <span className="text-xs text-kg-muted">Expected Payoff</span>
                  <span className="text-sm font-mono font-bold text-kg-muted">--</span>
               </div>
               <div className="flex items-center justify-between">
                  <span className="text-xs text-kg-muted">Sharpe Ratio</span>
                  <span className="text-sm font-mono font-bold text-kg-muted">--</span>
               </div>
            </div>
         </div>
         
         <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl p-6 shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
            <h3 className="text-sm font-bold text-kg-text flex items-center gap-2 mb-6">
              <ShieldAlert size={16} className="text-kg-danger" />
              Risk Limits
            </h3>
            <div className="space-y-6">
               <div className="space-y-2">
                  <div className="flex justify-between text-[10px] uppercase font-bold text-kg-muted">
                     <span>Daily Drawdown</span>
                     <span className="text-kg-text">0.00% / 0.00%</span>
                  </div>
                  <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                     <div className="h-full bg-kg-gold w-[0%]" />
                  </div>
               </div>
               <div className="space-y-2">
                  <div className="flex justify-between text-[10px] uppercase font-bold text-kg-muted">
                     <span>Max Exposure</span>
                     <span className="text-kg-text">$0.00 / $0.00</span>
                  </div>
                  <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                     <div className="h-full bg-kg-info w-[0%]" />
                  </div>
               </div>
            </div>
         </div>

         <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl p-6 shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
            <h3 className="text-sm font-bold text-kg-text flex items-center gap-2 mb-6">
              <Target size={16} className="text-kg-gold" />
              Symbol Affinity
            </h3>
            <div className="flex items-center justify-center h-24">
               <span className="text-kg-muted text-xs italic">Asset distribution chart...</span>
            </div>
         </div>
      </div>

      <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl overflow-hidden shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
        <div className="p-6 border-b border-kg-border flex items-center justify-between">
          <h3 className="text-sm font-bold text-kg-text flex items-center gap-2">
            <History size={16} className="text-kg-gold" />
            Trade History
          </h3>
          <button className="px-3 py-1 bg-white/5 hover:bg-white/10 rounded text-[10px] font-bold uppercase tracking-widest transition-all">Filter History</button>
        </div>
        <div className="p-0">
          <table className="w-full text-left">
            <thead className="text-[10px] text-kg-gold uppercase tracking-[0.15em] bg-[rgba(255,140,0,0.04)] border-b border-kg-border">
              <tr>
                <th className="px-6 py-4 font-extrabold">Ticket</th>
                <th className="px-6 py-4 font-extrabold">Symbol</th>
                <th className="px-6 py-4 font-extrabold">Side</th>
                <th className="px-6 py-4 text-right font-extrabold">Volume</th>
                <th className="px-6 py-4 text-right font-extrabold">P&L</th>
                <th className="px-6 py-4 text-right font-extrabold">Time</th>
              </tr>
            </thead>
            <tbody className="text-xs divide-y divide-kg-border">
              <tr>
                <td colSpan="6" className="px-6 py-12 text-center">
                  <div className="flex items-center justify-center mb-3">
                    <History size={24} className="text-kg-muted opacity-20" />
                  </div>
                  <p className="text-kg-muted text-sm italic">No trading history available</p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PortfolioPanel;

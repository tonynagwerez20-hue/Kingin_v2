import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, Wallet, BarChart3, Zap, Clock, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import useStore from '../../store/useStore';

const StatCard = ({ label, value, subvalue, icon: Icon, trend, color = 'kg-gold' }) => (
  <motion.div 
    whileHover={{ y: -5, scale: 1.02 }}
    className="bg-kg-panel backdrop-blur-xl border border-kg-border p-6 rounded-[2rem] relative overflow-hidden group transition-all duration-300 shadow-lg shadow-black/20"
  >
    {/* Decorative Glow */}
    <div className={`absolute -right-4 -top-4 w-16 h-16 bg-${color}/5 blur-2xl group-hover:bg-${color}/10 transition-all rounded-full`} />
    
    <div className="flex items-start justify-between relative z-10">
      <div className="flex-1">
        <p className="text-[10px] font-bold text-kg-muted uppercase tracking-[0.2em] mb-2">{label}</p>
        <h3 className="text-2xl font-black font-mono text-white tracking-tighter">{value}</h3>
        <div className="flex items-center gap-2 mt-3">
          {trend !== undefined && (
            <span className={`text-[10px] font-black flex items-center gap-0.5 px-2 py-0.5 rounded-lg ${
              trend > 0 ? 'bg-kg-success/10 text-kg-success' : 'bg-kg-danger/10 text-kg-danger'
            }`}>
              {trend > 0 ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
              {Math.abs(trend)}%
            </span>
          )}
          <span className="text-[10px] font-semibold text-kg-muted">{subvalue}</span>
        </div>
      </div>
      <div className={`p-3.5 rounded-2xl bg-white/[0.03] border border-kg-border text-${color} group-hover:border-${color}/50 transition-all shadow-inner`}>
        <Icon size={20} />
      </div>
    </div>
  </motion.div>
);

const Overview = () => {
  const { account, positions, prices, equityHistory } = useStore();

  const formatCurrency = (val) => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(val);

  const chartData = equityHistory?.length ? equityHistory : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-kg-text">Trading Overview</h1>
          <p className="text-sm text-kg-muted">Welcome back. Your portfolio is currently performing within parameters.</p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-xs font-medium border border-white/5 transition-all">
            Export Report
          </button>
          <button className="px-4 py-2 bg-kg-gold text-kg-dark hover:bg-kg-gold/90 rounded-lg text-xs font-bold transition-all shadow-[0_0_20px_rgba(255,215,0,0.2)]">
            New Strategy
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          label="Total Balance" 
          value={formatCurrency(account.balance)} 
          subvalue="Settled funds"
          icon={Wallet}
        />
        <StatCard 
          label="Session P&L" 
          value={`${account.todayPnl >= 0 ? '+' : ''}${formatCurrency(account.todayPnl)}`} 
          subvalue="Daily variation"
          icon={TrendingUp}
          trend={2.4}
          color="kg-success"
        />
        <StatCard 
          label="Open Positions" 
          value={account.openPositions} 
          subvalue="Live trades"
          icon={Zap}
          color="kg-info"
        />
        <StatCard 
          label="Win Rate" 
          value={account.winRate > 0 ? `${account.winRate.toFixed(1)}%` : '0.00%'} 
          subvalue="Last 30 days"
          icon={BarChart3}
          color="kg-warning"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-kg-panel backdrop-blur-xl border border-kg-border rounded-[2rem] overflow-hidden shadow-xl shadow-black/20 transition-all duration-300 hover:border-kg-gold/20">
            <div className="p-8 border-b border-kg-border flex items-center justify-between bg-white/[0.01]">
              <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-kg-gold shadow-[0_0_8px_#5D5FEF]" />
                Live Positions
              </h3>
              <button className="text-[10px] text-kg-gold font-black uppercase tracking-widest hover:text-white transition-colors bg-kg-gold/10 px-3 py-1.5 rounded-lg border border-kg-gold/20">View All</button>
            </div>
            <div className="p-0">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] text-kg-muted uppercase tracking-[0.2em] bg-white/[0.02]">
                    <th className="px-8 py-5 font-black">Symbol</th>
                    <th className="px-8 py-5 font-black">Side</th>
                    <th className="px-8 py-5 font-black text-right">Volume</th>
                    <th className="px-8 py-5 font-black text-right">Profit</th>
                  </tr>
                </thead>
                <tbody className="text-xs divide-y divide-kg-border/50">
                  {positions.length > 0 ? positions.map((p, i) => (
                    <tr key={i} className="hover:bg-white/[0.03] transition-colors group">
                      <td className="px-8 py-5 font-bold text-white group-hover:text-kg-gold transition-colors">{p.symbol}</td>
                      <td className="px-8 py-5">
                        <span className={`px-3 py-1 rounded-lg text-[10px] font-black tracking-widest ${
                          (p.type || p.direction) === 'BUY' ? 'bg-kg-success/10 text-kg-success border border-kg-success/20' : 'bg-kg-danger/10 text-kg-danger border border-kg-danger/20'
                        }`}>
                          {(p.type || p.direction)}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-right font-mono font-bold text-kg-muted">{p.lots || p.volume}</td>
                      <td className={`px-8 py-5 text-right font-mono font-black ${(p.floating_pnl || p.pnl || 0) >= 0 ? 'text-kg-success' : 'text-kg-danger'}`}>
                        {(p.floating_pnl || p.pnl || 0) >= 0 ? '+' : ''}${(p.floating_pnl || p.pnl || 0).toFixed(2)}
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan="4" className="px-8 py-12 text-center text-kg-muted italic font-medium">No active positions found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        </div>

        <div className="space-y-6">
          <div className="bg-kg-panel backdrop-blur-xl border border-kg-border rounded-[2rem] p-6 shadow-xl shadow-black/20">
            <h3 className="text-sm font-black text-white flex items-center gap-3 mb-6 uppercase tracking-widest">
              <Clock size={18} className="text-kg-gold" />
              Market Watch
            </h3>
            <div className="space-y-3">
               {Object.keys(prices || {}).length > 0 ? (
                 Object.keys(prices).map((symbol) => {
                    const data = prices[symbol];
                    return (
                      <div key={symbol} className="flex items-center justify-between p-4 rounded-2xl bg-white/[0.02] border border-white/[0.05] hover:border-kg-gold/30 transition-all group">
                         <div className="flex flex-col">
                           <span className="text-xs font-black text-white tracking-wide">{symbol}</span>
                           <span className={`text-[10px] font-bold ${data.change >= 0 ? 'text-kg-success' : 'text-kg-danger'}`}>
                             {data.change >= 0 ? '+' : ''}{data.change?.toFixed(2) || '0.00'}%
                           </span>
                         </div>
                         <div className="text-right">
                           <div className="text-sm font-mono font-black text-kg-gold group-hover:scale-105 transition-transform">{data.bid?.toFixed(5) || '0.00000'}</div>
                           <div className="text-[9px] font-bold text-kg-muted uppercase tracking-tighter">SPREAD: {((data.ask - data.bid) * 10000).toFixed(1) || '--'}</div>
                         </div>
                      </div>
                    );
                 })
               ) : (
                 <div className="flex flex-col items-center justify-center p-10 border-2 border-white/[0.03] border-dashed rounded-[2rem] opacity-50 bg-white/[0.01]">
                   <Zap size={24} className="text-kg-muted mb-2 animate-pulse" />
                   <span className="text-[10px] font-bold text-kg-muted uppercase tracking-widest italic">Waiting for feed</span>
                 </div>
               )}
            </div>
          </div>
          
          <div className="bg-gradient-to-br from-kg-gold/20 to-transparent backdrop-blur-xl border border-kg-gold/20 rounded-[2rem] p-6 relative overflow-hidden group">
             <div className="absolute -right-10 -bottom-10 w-32 h-32 bg-kg-gold/10 blur-3xl rounded-full group-hover:bg-kg-gold/20 transition-all" />
             <div className="flex items-center gap-3 mb-3 relative z-10">
                <div className="p-2 bg-kg-gold/20 rounded-xl">
                  <Zap size={18} className="text-kg-gold" />
                </div>
                <span className="text-xs font-black text-white tracking-[0.2em] uppercase">AI Insight</span>
             </div>
             <p className="text-xs text-kg-text leading-relaxed font-medium relative z-10">
                {account.bias === 'BULLISH' ? 'Neural engine detects structural bullish expansion. ' : account.bias === 'BEARISH' ? 'Structural bearish pressure identified by H1 Bias layer. ' : 'Market is currently in a neutral consolidation phase. '}
                {account.regime === 'TRENDING' ? 'High probability trend-following environment active. ' : account.regime === 'VOLATILE' ? 'High volatility detected; execution thresholds increased for safety. ' : 'Stable conditions confirmed across all liquidity nodes. '}
                Targeting high-confluence zones aligned with institutional orderflow.
             </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;

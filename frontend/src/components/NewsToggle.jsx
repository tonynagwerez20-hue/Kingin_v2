import React from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Zap } from 'lucide-react';

const NewsToggle = ({ participate, onChange, disabled }) => {
  return (
    <div className="flex flex-col gap-4 p-6 bg-white/[0.03] border border-white/5 rounded-2xl transition-all hover:bg-white/[0.05]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${participate ? 'bg-kg-success/10 text-kg-success' : 'bg-kg-warning/10 text-kg-warning'}`}>
            {participate ? <Zap size={20} /> : <AlertTriangle size={20} />}
          </div>
          <div>
            <h4 className="text-xs font-black text-white uppercase tracking-widest">News Strategy</h4>
            <p className="text-[10px] text-kg-muted font-medium mt-0.5">
              {participate ? 'Participating in news volatility' : 'Sitting out during news events'}
            </p>
          </div>
        </div>
        
        <button
          onClick={() => !disabled && onChange(!participate)}
          className={`relative w-12 h-6 rounded-full transition-all duration-300 ${
            participate ? 'bg-kg-gold' : 'bg-white/10'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <motion.div
            animate={{ x: participate ? 26 : 4 }}
            className={`absolute top-1 w-4 h-4 rounded-full shadow-lg ${
              participate ? 'bg-black' : 'bg-kg-muted'
            }`}
          />
        </button>
      </div>
      
      <div className="bg-black/20 rounded-xl p-3 border border-white/5">
        <p className="text-[9px] leading-relaxed text-kg-muted/80">
          <span className="font-bold text-kg-gold">PROTECTIVE MODE (SIT OUT):</span> Blocks trading 5m before high-impact events to avoid spread spikes.<br/>
          <span className="font-bold text-kg-success">VOLATILITY MODE (PARTICIPATE):</span> Ignores time-blocks and attempts news scalps if enabled.
        </p>
      </div>
    </div>
  );
};

export default NewsToggle;

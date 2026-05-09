import React, { useRef, useEffect } from 'react';
import { Terminal, Shield, Cpu, RefreshCw, Trash2, Search } from 'lucide-react';
import useStore from '../../store/useStore';

const LogItem = ({ log }) => {
  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR': return 'text-kg-danger';
      case 'WARN': return 'text-kg-warning';
      case 'TRADE': return 'text-kg-success';
      case 'DEBUG': return 'text-kg-info';
      default: return 'text-kg-muted';
    }
  };

  const formatTime = (ts) => new Date(ts).toLocaleTimeString('en-US', { hour12: false });

  return (
    <div className="flex items-start gap-3 py-2 px-4 hover:bg-white/2 transition-colors border-b border-white/5 last:border-0 font-mono text-[11px]">
      <span className="text-kg-muted shrink-0 w-20">{formatTime(log.time)}</span>
      <span className={`font-bold shrink-0 w-16 ${getLevelColor(log.level)}`}>[{log.level}]</span>
      <span className="text-kg-gold shrink-0 w-24">({log.module})</span>
      <span className="text-kg-text break-all">{log.message}</span>
    </div>
  );
};

const SystemPanel = () => {
  const { logs, isEngineRunning } = useStore();
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="h-full flex flex-col space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-kg-text">System Logs</h1>
          <p className="text-sm text-kg-muted">Real-time telemetry and engine diagnostics.</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-kg-muted" size={14} />
            <input 
              type="text" 
              placeholder="Filter logs..."
              className="bg-white/5 border border-white/5 rounded-lg pl-9 pr-4 py-2 text-xs focus:border-kg-gold/50 outline-none transition-all w-64"
            />
          </div>
          <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-kg-muted transition-all">
            <Trash2 size={18} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl p-6 flex items-center gap-4 shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
          <div className="p-3 bg-kg-gold/10 text-kg-gold rounded-xl">
            <Cpu size={24} />
          </div>
          <div>
            <p className="text-[10px] text-kg-muted uppercase tracking-widest">Engine Load</p>
            <h4 className="text-xl font-bold font-mono">{isEngineRunning ? (Math.random() * 5 + 8).toFixed(1) : '0.0'}%</h4>
          </div>
        </div>
        <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl p-6 flex items-center gap-4 shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
          <div className={`p-3 rounded-xl ${isEngineRunning ? 'bg-kg-success/10 text-kg-success' : 'bg-kg-danger/10 text-kg-danger'}`}>
            <RefreshCw size={24} className={isEngineRunning ? 'animate-spin-slow' : ''} />
          </div>
          <div>
            <p className="text-[10px] text-kg-muted uppercase tracking-widest">Uptime</p>
            <h4 className="text-xl font-bold font-mono">
              {(() => {
                const s = useStore.getState().engineUptimeSeconds;
                const h = Math.floor(s / 3600).toString().padStart(2, '0');
                const m = Math.floor((s % 3600) / 60).toString().padStart(2, '0');
                const sec = (s % 60).toString().padStart(2, '0');
                return `${h}h ${m}m ${sec}s`;
              })()}
            </h4>
          </div>
        </div>
        <div className="bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl p-6 flex items-center gap-4 shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
          <div className="p-3 bg-kg-info/10 text-kg-info rounded-xl">
            <Shield size={24} />
          </div>
          <div>
            <p className="text-[10px] text-kg-muted uppercase tracking-widest">Security Status</p>
            <h4 className="text-xl font-bold font-mono">{isEngineRunning ? 'ENCRYPTED' : 'OFFLINE'}</h4>
          </div>
        </div>
      </div>

      <div className="flex-1 bg-kg-surface/40 backdrop-blur-md border border-kg-border rounded-xl overflow-hidden flex flex-col shadow-[0_12px_40px_rgba(0,0,0,0.4)]">
        <div className="p-4 border-b border-kg-border flex items-center gap-3 bg-[rgba(255,140,0,0.04)]">
          <Terminal size={16} className="text-kg-gold" />
          <span className="text-xs font-extrabold uppercase tracking-[0.25em] text-kg-gold">Console Output</span>
          <div className="ml-auto flex gap-4 text-[10px] font-bold">
            <span className="text-kg-success flex items-center gap-1">● TRADE</span>
            <span className="text-kg-warning flex items-center gap-1">● WARN</span>
            <span className="text-kg-danger flex items-center gap-1">● ERROR</span>
          </div>
        </div>
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto custom-scrollbar bg-black/20"
        >
          {logs.length > 0 ? (
            logs.map((log, i) => <LogItem key={i} log={log} />)
          ) : (
            <div className="h-full flex items-center justify-center flex-col gap-4">
              <Terminal size={40} className="text-kg-muted opacity-20" />
              <p className="text-kg-muted text-xs italic">Waiting for system telemetry...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SystemPanel;

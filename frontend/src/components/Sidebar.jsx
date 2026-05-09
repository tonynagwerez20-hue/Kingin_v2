import React from 'react';
import { motion } from 'framer-motion';
import { 
  LayoutDashboard, 
  TrendingUp, 
  PieChart, 
  Cpu, 
  Terminal, 
  Settings, 
  Menu,
  ChevronLeft,
  RefreshCw
} from 'lucide-react';
import useStore from '../store/useStore';

const SidebarItem = ({ id, icon: Icon, label, active, onClick, expanded }) => (
  <button
    onClick={() => onClick(id)}
    className={`
      flex items-center w-full px-4 py-3 mb-2 transition-all duration-300 relative group
      ${active 
        ? 'text-kg-gold' 
        : 'text-kg-muted hover:text-kg-text'}
    `}
  >
    {active && (
      <motion.div
        layoutId="active-pill"
        className="absolute inset-0 bg-kg-gold/10 rounded-xl"
        initial={false}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
      />
    )}
    {active && (
      <div className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-kg-gold rounded-r-full shadow-[0_0_10px_#5D5FEF]" />
    )}
    <Icon size={20} className={`z-10 ${active ? 'text-kg-gold' : 'group-hover:scale-110 transition-transform'}`} />
    {expanded && (
      <motion.span
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        className="ml-3 font-semibold text-sm whitespace-nowrap z-10"
      >
        {label}
      </motion.span>
    )}
  </button>
);

const Sidebar = () => {
  const { activePanel, setActivePanel, sidebarExpanded, toggleSidebar, isEngineRunning, isBridgeConnected, startEngine, stopEngine, syncWithEngine } = useStore();

  const menuItems = [
    { id: 'overview', icon: LayoutDashboard, label: 'Overview' },
    { id: 'trading', icon: TrendingUp, label: 'Trading' },
    { id: 'portfolio', icon: PieChart, label: 'Portfolio' },
    { id: 'intelligence', icon: Cpu, label: 'Intelligence' },
    { id: 'system', icon: Terminal, label: 'System Logs' },
  ];

  return (
    <motion.aside
      animate={{ width: sidebarExpanded ? 260 : 80 }}
      className="h-screen bg-kg-dark/40 backdrop-blur-xl border-r border-kg-border flex flex-col p-4 z-50 relative overflow-hidden"
    >
      {/* Background Glow */}
      <div className="absolute -left-20 -top-20 w-40 h-40 bg-kg-gold/10 blur-[80px] rounded-full pointer-events-none" />

      <div className="flex items-center justify-between mb-10 px-2">
        {sidebarExpanded && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-3"
          >
            <div className="w-10 h-10 bg-gradient-to-br from-kg-gold to-kg-gold-muted rounded-xl flex items-center justify-center shadow-lg shadow-kg-gold/20">
              <span className="font-black text-white text-xl">K</span>
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-sm tracking-widest text-white leading-none">KINGIN</span>
              <span className="text-[10px] text-kg-gold font-bold uppercase tracking-tighter">PRO+ DASHBOARD</span>
            </div>
          </motion.div>
        )}
        <button 
          onClick={toggleSidebar}
          className="p-2.5 hover:bg-white/5 rounded-xl text-kg-muted hover:text-white transition-all"
        >
          {sidebarExpanded ? <ChevronLeft size={20} /> : <Menu size={20} />}
        </button>
      </div>

      <nav className="flex-1">
        {menuItems.map((item) => (
          <SidebarItem
            key={item.id}
            {...item}
            active={activePanel === item.id}
            onClick={setActivePanel}
            expanded={sidebarExpanded}
          />
        ))}
      </nav>

      <div className="mt-auto space-y-4 pt-4 border-t border-kg-border/50">
        {/* Master Control */}
        <div className={`p-4 rounded-2xl border border-kg-border bg-white/[0.02] transition-all ${sidebarExpanded ? 'block' : 'hidden'}`}>
          <div className="flex flex-col gap-1.5 mb-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-kg-muted uppercase tracking-wider">Engine Status</span>
              <div className={`w-2 h-2 rounded-full ${isEngineRunning ? 'bg-kg-success shadow-[0_0_8px_#00E676]' : 'bg-kg-danger shadow-[0_0_8px_#FF5252]'}`} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-kg-muted uppercase tracking-wider">MT5 EA Bridge</span>
              <div className={`w-2 h-2 rounded-full ${isBridgeConnected ? 'bg-kg-success shadow-[0_0_8px_#00E676]' : 'bg-kg-warning shadow-[0_0_8px_#FFD740]'}`} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={startEngine}
              disabled={isEngineRunning}
              className={`py-2 rounded-xl text-[10px] font-black transition-all ${
                isEngineRunning 
                  ? 'bg-kg-muted/10 text-kg-muted cursor-not-allowed' 
                  : 'bg-kg-success/10 text-kg-success hover:bg-kg-success hover:text-black shadow-lg shadow-kg-success/10 hover:shadow-kg-success/30'
              }`}
            >
              START
            </button>
            <button
              onClick={stopEngine}
              disabled={!isEngineRunning}
              className={`py-2 rounded-xl text-[10px] font-black transition-all ${
                !isEngineRunning 
                  ? 'bg-kg-muted/10 text-kg-muted cursor-not-allowed' 
                  : 'bg-kg-danger/10 text-kg-danger hover:bg-kg-danger hover:text-white shadow-lg shadow-kg-danger/10 hover:shadow-kg-danger/30'
              }`}
            >
              STOP
            </button>
          </div>
        </div>

        <SidebarItem
          id="settings"
          icon={Settings}
          label="Settings"
          active={activePanel === 'settings'}
          onClick={setActivePanel}
          expanded={sidebarExpanded}
        />
        
        <button 
          onClick={syncWithEngine}
          className={`
            flex items-center w-full px-4 py-3 mt-4 transition-all duration-300 relative group
            text-kg-gold/60 hover:text-kg-gold bg-kg-gold/5 hover:bg-kg-gold/10 rounded-2xl border border-kg-gold/10
          `}
        >
          <RefreshCw size={20} className="group-hover:rotate-180 transition-transform duration-700" />
          {sidebarExpanded && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="ml-3 font-black text-[10px] uppercase tracking-widest"
            >
              Sync System
            </motion.span>
          )}
        </button>
      </div>
    </motion.aside>
  );
};

export default Sidebar;

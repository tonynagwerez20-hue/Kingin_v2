"""
Hedge Trading System Supervisor
Monitors all system components and automatically restarts them on failure.
Includes logging, crash detection, and configurable restart policies.
"""
import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import threading
from core.alert_manager import alert_manager

# --- CONFIG ---
from config.settings import PROJECT_ROOT, LOG_DIR
from core.alert_manager import alert_manager

# Configuration
MAX_RESTART_ATTEMPTS = 5  # Max restarts within the time window
RESTART_WINDOW_SECONDS = 300  # 5 minutes
RESTART_DELAY_SECONDS = 5  # Wait before restarting
HEALTH_CHECK_INTERVAL = 10  # Check process health every 10 seconds

class ProcessMonitor:
    """Monitors a single process and handles restarts."""
    
    def __init__(self, name, command, cwd=None):
        self.name = name
        self.command = command
        self.cwd = cwd or PROJECT_ROOT
        self.process = None
        self.restart_history = []
        self.start_time = None
        
    def start(self):
        """Start or restart the process."""
        try:
            logger.info(f"Starting {self.name}...")
            
            if sys.platform == 'win32':
                self.process = subprocess.Popen(
                    self.command,
                    cwd=self.cwd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                self.process = subprocess.Popen(
                    self.command,
                    cwd=self.cwd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            self.start_time = time.time()
            logger.info(f"[OK] {self.name} started (PID: {self.process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Failed to start {self.name}: {e}")
            return False
    
    def is_running(self):
        """Check if process is still running."""
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def should_restart(self):
        """Determine if process should be restarted based on restart policy."""
        # Clean old restart history outside the time window
        current_time = time.time()
        self.restart_history = [
            t for t in self.restart_history 
            if current_time - t < RESTART_WINDOW_SECONDS
        ]
        
        # Check if we've exceeded max restarts
        if len(self.restart_history) >= MAX_RESTART_ATTEMPTS:
            logger.error(
                f"[WARN] {self.name} has crashed {MAX_RESTART_ATTEMPTS} times "
                f"in {RESTART_WINDOW_SECONDS}s. Giving up."
            )
            return False
        
        return True
    
    def restart(self):
        """Restart the process with backoff."""
        if not self.should_restart():
            self.is_manual_wait = True
            alert_manager.send_email(
                f"COMPONENT CRITICAL: {self.name}",
                f"{self.name} has crashed {MAX_RESTART_ATTEMPTS} times and is now in MANUAL WAIT mode."
            )
            return False
        
        logger.warning(f"Restarting {self.name} in {RESTART_DELAY_SECONDS}s...")
        time.sleep(RESTART_DELAY_SECONDS)
        
        self.restart_history.append(time.time())
        started = self.start()
        if not started:
            alert_manager.send_email(
                f"COMPONENT RESTART FAILED: {self.name}",
                f"Failed to restart {self.name}. Check logs for details."
            )
        return started
    
    def force_restart(self):
        """Manually force a restart regardless of policy."""
        logger.info(f"Manually forcing restart of {self.name}...")
        self.restart_history = []
        self.is_manual_wait = False
        return self.start()
    
    def stop(self):
        """Stop the process gracefully."""
        if self.process:
            logger.info(f"Stopping {self.name}...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
                logger.info(f"✓ {self.name} stopped")
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {self.name}...")
                self.process.kill()
    
    def get_uptime(self):
        """Get process uptime in seconds."""
        if self.start_time and self.is_running():
            return time.time() - self.start_time
        return 0

class SystemSupervisor:
    """Supervises all system components."""
    
    def __init__(self):
        self.monitors = []
        self.running = False
        
        # Determine Python executable
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        self.python_cmd = str(venv_python) if venv_python.exists() else sys.executable
        
    def add_component(self, name, script_path):
        """Add a component to monitor."""
        if not script_path.exists():
            logger.warning(f"[WARN] {name} script not found at {script_path}")
            return
        
        monitor = ProcessMonitor(
            name=name,
            command=[self.python_cmd, str(script_path)]
        )
        self.monitors.append(monitor)
        logger.info(f"Added {name} to supervision")
    
    def start_all(self):
        """Start all monitored components."""
        logger.info("="*60)
        logger.info("STARTING SUPERVISED SYSTEM")
        logger.info("="*60)
        
        for monitor in self.monitors:
            monitor.start()
            time.sleep(2)  # Stagger starts
        
        self.running = True
        logger.info(f"All {len(self.monitors)} components started")
        
        # Start command listener thread
        self.cmd_thread = threading.Thread(target=self.command_listener, daemon=True)
        self.cmd_thread.start()
    
    def command_listener(self):
        """Listen for console commands."""
        while self.running:
            try:
                cmd = input().strip().lower()
                if cmd == 's' or cmd == 'status':
                    self.log_status()
                elif cmd == 'r all' or cmd == 'restart all':
                    for m in self.monitors:
                        m.force_restart()
                elif cmd.startswith('restart '):
                    name = cmd.split(' ', 1)[1]
                    for m in self.monitors:
                        if m.name.lower() == name.lower():
                            m.force_restart()
                elif cmd == 'q' or cmd == 'quit':
                    self.running = False
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Command error: {e}")
    
    def monitor_loop(self):
        """Main monitoring loop."""
        logger.info("\n" + "="*60)
        logger.info("SUPERVISOR ACTIVE - Monitoring system health")
        logger.info(f"Health checks every {HEALTH_CHECK_INTERVAL}s")
        logger.info("Press Ctrl+C to stop supervision")
        logger.info("="*60 + "\n")
        
        try:
            while self.running:
                time.sleep(HEALTH_CHECK_INTERVAL)
                
                for monitor in self.monitors:
                    if not monitor.is_running() and not getattr(monitor, 'is_manual_wait', False):
                        uptime = monitor.get_uptime()
                        logger.error(
                            f"[WARN] {monitor.name} has crashed! "
                            f"(Uptime: {uptime:.1f}s)"
                        )
                        
                        if monitor.restart():
                            logger.info(f"[OK] {monitor.name} restarted successfully")
                        else:
                            logger.error(f"[FAIL] {monitor.name} entered MANUAL WAIT mode")
                
                # Non-blocking input check would be complex here without threading,
                # but we can check if any component is in manual wait and prompt.
                manual_count = sum(1 for m in self.monitors if getattr(m, 'is_manual_wait', False))
                if manual_count > 0:
                    logger.warning(f"Attention: {manual_count} components are in MANUAL WAIT mode.")
                    logger.info("Type 'restart <name>' or 'r all' to try again.")
                
                # Periodic status update
                if int(time.time()) % 60 == 0:  # Every minute
                    self.log_status()
                    print("\nCommands: [s]tatus, [r]estart all, [q]uit")
        
        except KeyboardInterrupt:
            logger.info("\n\nShutdown signal received...")
            self.shutdown()
    
    def log_status(self):
        """Log current system status."""
        logger.info("\n" + "-"*60)
        logger.info("SYSTEM STATUS")
        logger.info("-"*60)
        
        for monitor in self.monitors:
            if monitor.is_running():
                uptime = monitor.get_uptime()
                restarts = len(monitor.restart_history)
                logger.info(
                    f"  [OK] {monitor.name}: Running "
                    f"(Uptime: {uptime:.0f}s, Restarts: {restarts})"
                )
            elif getattr(monitor, 'is_manual_wait', False):
                logger.error(f"  [MANUAL WAIT] {monitor.name}: CRASHED (Max retries reached)")
            else:
                logger.warning(f"  [FAIL] {monitor.name}: Stopped")
        
        logger.info("-"*60 + "\n")
    
    def shutdown(self):
        """Shutdown all components."""
        self.running = False
        logger.info("Stopping all components...")
        
        for monitor in self.monitors:
            monitor.stop()
        
        logger.info("✓ Supervisor shutdown complete")

def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║      HEDGE TRADING SYSTEM SUPERVISOR                      ║
    ║      Auto-restart enabled for all components              ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    logger.info(f"Log file: {log_file}")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"Max restarts: {MAX_RESTART_ATTEMPTS} per {RESTART_WINDOW_SECONDS}s")
    
    # Create supervisor
    supervisor = SystemSupervisor()
    
    # Add components
    supervisor.add_component(
        "Data Feed Server",
        PROJECT_ROOT.parent / "networking" / "server.py"
    )
    
    supervisor.add_component(
        "Trading Engine",
        PROJECT_ROOT.parent / "core" / "main_loop.py"
    )
    
    # 3. Add Dashboard (Streamlit doesn't run via regular python script but via module)
    dashboard_path = PROJECT_ROOT / "dashboard" / "dashboard.py"
    if dashboard_path.exists():
        monitor = ProcessMonitor(
            name="Dashboard",
            command=[supervisor.python_cmd, "-m", "streamlit", "run", str(dashboard_path)]
        )
        supervisor.monitors.append(monitor)
        logger.info("Added Dashboard to supervision")
    
    # Start and monitor
    supervisor.start_all()
    supervisor.monitor_loop()

if __name__ == "__main__":
    main()

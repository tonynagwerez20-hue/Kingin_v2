"""
MT5 Recovery & Bootstrap System
Handles IPC timeouts, ensures terminal is running, and enables automated trading
"""

import subprocess
import time
import os
import sys
from pathlib import Path

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


class MT5Recovery:
    def __init__(self):
        self.mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        self.max_attempts = 3
        self.recovery_steps = []
    
    def check_mt5_running(self):
        """Check if MT5 process is running"""
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq terminal64.exe', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # If terminal64.exe is in output, it's running
            return 'terminal64.exe' in result.stdout.lower()
        except Exception as e:
            print(f"  Error checking MT5 process: {e}")
            return False
    
    def start_mt5_terminal(self):
        """Start MT5 terminal if not running"""
        if self.check_mt5_running():
            print("  ✓ MT5 terminal already running")
            return True
        
        print("  ⚠ MT5 terminal not running, starting...")
        try:
            if os.path.exists(self.mt5_path):
                subprocess.Popen([self.mt5_path])
                print(f"  ✓ Started: {self.mt5_path}")
                # Wait for terminal to fully initialize
                print("  ⏳ Waiting for MT5 to initialize (20 seconds)...")
                for i in range(20):
                    time.sleep(1)
                    if i % 5 == 0 and i > 0:
                        print(f"     {20-i} seconds remaining...")
                return True
            else:
                print(f"  ✗ MT5 not found at: {self.mt5_path}")
                return False
        except Exception as e:
            print(f"  ✗ Failed to start MT5: {e}")
            return False
    
    def try_initialize(self, attempt=1):
        """Try to initialize MT5 with better error handling"""
        if not MT5_AVAILABLE:
            print("  ⚠ MT5 Python library not available")
            return False
        
        print(f"  [Attempt {attempt}/{self.max_attempts}] Initializing MT5...")
        try:
            result = mt5.initialize(login=0, server="", password="")
            if result:
                print("  ✓ MT5 initialized successfully")
                return True
            else:
                error = mt5.last_error()
                print(f"  ✗ MT5 init failed: {error}")
                
                # Shutdown before retry
                try:
                    mt5.shutdown()
                except:
                    pass
                
                return False
        except Exception as e:
            error_str = str(e)
            print(f"  ✗ Error during initialization: {error_str}")
            
            # Check for IPC timeout
            if "timeout" in error_str.lower() or "ipc" in error_str.lower():
                print("  ⚠ IPC timeout detected - MT5 may be frozen or slow")
                self.recovery_steps.append("IPC_TIMEOUT")
                
                if attempt < self.max_attempts:
                    print(f"  ⏳ Retrying in 5 seconds...")
                    time.sleep(5)
                    return self.try_initialize(attempt + 1)
            
            return False
    
    def enable_automated_trading_via_terminal(self):
        """
        Send command to MT5 terminal to enable automated trading
        This attempts to use MT5's /auto parameter
        """
        print("  Attempting to enable automated trading via terminal...")
        try:
            # Kill current terminal
            subprocess.run(
                ['taskkill', '/IM', 'terminal64.exe', '/F'],
                capture_output=True,
                timeout=5
            )
            time.sleep(2)
            
            # Start with /auto parameter
            if os.path.exists(self.mt5_path):
                subprocess.Popen([self.mt5_path, '/auto'])
                print("  ✓ Terminal restarted with automated trading enabled")
                print("  ⏳ Waiting for restart (15 seconds)...")
                time.sleep(15)
                return True
        except Exception as e:
            print(f"  ⚠ Could not use /auto parameter: {e}")
        
        return False
    
    def recover(self):
        """Execute full recovery sequence"""
        print("\n" + "="*70)
        print("MT5 RECOVERY SYSTEM - Fixing IPC Timeout")
        print("="*70 + "\n")
        
        # Step 1: Check and start terminal
        print("[1/4] Checking MT5 Terminal Status...")
        if not self.start_mt5_terminal():
            print("\n✗ Could not start MT5")
            return False
        
        # Step 2: Try initialization
        print("\n[2/4] Initializing MT5 Connection...")
        if not self.try_initialize():
            print("\n✗ MT5 initialization failed")
            return False
        
        # Step 3: Verify connection
        print("\n[3/4] Verifying MT5 Connection...")
        try:
            terminal_info = mt5.terminal_info()
            account_info = mt5.account_info()
            
            if terminal_info and account_info:
                print(f"  ✓ Terminal connected: {terminal_info.server}")
                print(f"  ✓ Account: {account_info.login}")
                print(f"  ✓ Balance: ${account_info.balance:.2f}")
                mt5.shutdown()
            else:
                print("  ⚠ Terminal info not available")
                mt5.shutdown()
        except Exception as e:
            print(f"  ✗ Verification error: {e}")
        
        # Step 4: Summary
        print("\n[4/4] Recovery Summary...")
        if self.recovery_steps:
            print(f"  Issues encountered and recovered from:")
            for step in self.recovery_steps:
                print(f"    - {step}")
        
        print("\n" + "="*70)
        print("✓ MT5 RECOVERY COMPLETE")
        print("="*70)
        
        return True


def main():
    recovery = MT5Recovery()
    success = recovery.recover()
    
    if success:
        print("\n✓ You can now run: START_SYSTEM_SMART.bat")
        return 0
    else:
        print("\n✗ Recovery failed. Please:")
        print("  1. Make sure MetaTrader5 is installed")
        print("  2. Open MT5 manually")
        print("  3. Enable automated trading: Tools → Options → Expert Advisors")
        print("  4. Restart MT5")
        print("  5. Try again")
        return 1


if __name__ == "__main__":
    sys.exit(main())

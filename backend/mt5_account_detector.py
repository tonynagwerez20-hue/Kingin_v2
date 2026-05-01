"""
Dynamic MT5 Account Detector
- Detects the currently logged-in MT5 account (any broker)
- Falls back to saved credentials if needed
- Makes the system broker-agnostic
"""

import json
import os
from pathlib import Path

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


class AccountDetector:
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = Path(__file__).parent
        else:
            project_root = Path(project_root)
        
        self.project_root = project_root
        self.runtime_creds_file = project_root / "runtime_credentials.json"
        self.config_file = project_root / "config" / "trading_params_lite.json"
    
    def detect_active_account(self):
        """
        Detect the currently logged-in MT5 account (any broker).
        Returns: {login, password, server, broker} or None
        """
        if not MT5_AVAILABLE:
            return None
        
        try:
            # Initialize MT5 with timeout handling
            if not mt5.initialize():
                error = mt5.last_error()
                if error and "timeout" in str(error).lower():
                    raise TimeoutError(f"MT5 IPC timeout: {error}")
                return None
            
            # Get current account info
            account_info = mt5.account_info()
            if not account_info:
                mt5.shutdown()
                return None
            
            # Get terminal info to get server name
            terminal_info = mt5.terminal_info()
            if not terminal_info:
                mt5.shutdown()
                return None
            
            # Extract broker name from server
            server = terminal_info.server
            broker = self._extract_broker(server)
            
            # Return detected credentials (note: password not accessible from MT5)
            detected = {
                "login": account_info.login,
                "server": server,
                "broker": broker,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "leverage": account_info.leverage,
            }
            
            mt5.shutdown()
            return detected
        except TimeoutError as e:
            print(f"[TIMEOUT] {e}")
            raise
        except Exception as e:
            print(f"Error detecting active account: {e}")
            return None
    
    @staticmethod
    def _extract_broker(server):
        """Extract broker name from MT5 server string"""
        server_lower = server.lower()
        if "exness" in server_lower:
            return "Exness"
        elif "icmarkets" in server_lower:
            return "ICMarkets"
        elif "pepperstone" in server_lower:
            return "Pepperstone"
        elif "oanda" in server_lower:
            return "OANDA"
        elif "fxprimus" in server_lower:
            return "FXPrimus"
        elif "just2trade" in server_lower:
            return "Just2Trade"
        elif "easymarkets" in server_lower:
            return "EasyMarkets"
        elif "hantec" in server_lower:
            return "Hantec"
        return "Unknown"
    
    def get_runtime_credentials(self):
        """Load credentials from runtime_credentials.json"""
        if not self.runtime_creds_file.exists():
            return None
        
        try:
            with open(self.runtime_creds_file, "r") as f:
                return json.load(f)
        except Exception:
            return None
    
    def get_active_credentials(self):
        """
        Get active credentials in priority order:
        1. Currently logged-in MT5 account (any broker, any account)
        2. Saved runtime credentials from last session
        Returns: {login, password, server, broker} or raises error
        """
        # Try to detect active MT5 account
        detected = self.detect_active_account()
        if detected and detected.get("login"):
            print(f"✓ Detected active MT5 account: {detected['login']} on {detected['broker']}")
            # Try to get password from runtime creds if they match
            runtime = self.get_runtime_credentials()
            if runtime and runtime.get("login") == detected["login"]:
                detected["password"] = runtime.get("password", "")
            return detected
        
        # Fall back to runtime credentials
        runtime = self.get_runtime_credentials()
        if runtime and runtime.get("login"):
            print(f"✓ Using runtime credentials: {runtime['login']} on {runtime.get('server')}")
            return runtime
        
        raise RuntimeError(
            "No active MT5 account detected and no saved credentials found. "
            "Please: 1) Log into MetaTrader5 with any broker, or "
            "2) Run mt5_auth.py to save credentials"
        )
    
    def update_config_with_active_account(self):
        """
        Update trading_params_lite.json with the currently active MT5 account.
        This makes the system work with any broker/account without hardcoding.
        """
        try:
            creds = self.get_active_credentials()
            
            # Load current config
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    config = json.load(f)
            else:
                config = {"pipeline": {"data_provider": {"config": {}}}}
            
            # Update credentials in config
            if "pipeline" not in config:
                config["pipeline"] = {}
            if "data_provider" not in config["pipeline"]:
                config["pipeline"]["data_provider"] = {}
            if "config" not in config["pipeline"]["data_provider"]:
                config["pipeline"]["data_provider"]["config"] = {}
            
            config["pipeline"]["data_provider"]["config"]["login"] = creds.get("login")
            config["pipeline"]["data_provider"]["config"]["server"] = creds.get("server")
            if creds.get("password"):
                config["pipeline"]["data_provider"]["config"]["password"] = creds.get("password")
            
            # Add broker info for reference
            config["pipeline"]["data_provider"]["config"]["broker"] = creds.get("broker")
            config["pipeline"]["data_provider"]["config"]["balance"] = creds.get("balance")
            config["pipeline"]["data_provider"]["config"]["leverage"] = creds.get("leverage")
            
            # Save updated config
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
            
            print(f"✓ Updated config with {creds.get('broker')} account {creds.get('login')}")
            return True
        except Exception as e:
            print(f"✗ Failed to update config: {e}")
            return False


def main():
    """Test the account detector"""
    detector = AccountDetector()
    
    print("=" * 60)
    print("MT5 ACCOUNT DETECTOR - Auto-detect any broker/account")
    print("=" * 60)
    
    # Detect active account
    detected = detector.detect_active_account()
    if detected:
        print(f"\nActive MT5 Account Detected:")
        print(f"  Login: {detected['login']}")
        print(f"  Broker: {detected['broker']}")
        print(f"  Server: {detected['server']}")
        print(f"  Balance: ${detected.get('balance', 0):,.2f}")
        print(f"  Leverage: 1:{detected.get('leverage', 0)}")
    else:
        print("\nNo active MT5 account detected")
    
    # Try to get active credentials
    try:
        creds = detector.get_active_credentials()
        print(f"\n✓ Active credentials available for: {creds['login']} on {creds['broker']}")
    except Exception as e:
        print(f"\n✗ No credentials available: {e}")
    
    # Update config
    print("\nAttempting to update trading config...")
    if detector.update_config_with_active_account():
        print("✓ Config updated successfully - system now uses active MT5 account")
    else:
        print("✗ Config update failed")


if __name__ == "__main__":
    main()

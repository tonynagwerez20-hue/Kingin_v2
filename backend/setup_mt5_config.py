"""
MT5 Configuration Setup
======================
Interactive script to configure MT5 credentials for the system.
Run once to set up your MT5 account details.

Usage: python setup_mt5_config.py
"""

import json
import sys
from pathlib import Path


def setup_mt5_config():
    """Interactive setup for MT5 credentials"""
    
    config_path = Path("config/trading_params_lite.json")
    
    print("\n" + "="*60)
    print("MT5 CREDENTIAL SETUP")
    print("="*60 + "\n")
    
    print("This script will help you configure MT5 credentials.\n")
    print("You can find these in your MetaTrader5 Terminal:")
    print("  • Account number: Look at window title or Tools > Options > Account")
    print("  • Password: Your MT5 login password")
    print("  • Server: Look at window title (e.g., 'Exness-MT5Trial9')\n")
    
    # Get MT5 details
    try:
        account = input("Enter MT5 Account Number (9 digits): ").strip()
        try:
            account = int(account)
        except ValueError:
            print("ERROR: Account must be a number!")
            return False
        
        password = input("Enter MT5 Password: ").strip()
        if not password:
            print("ERROR: Password cannot be empty!")
            return False
        
        server = input("Enter MT5 Server (e.g., Exness-MT5Trial9): ").strip()
        if not server:
            print("ERROR: Server cannot be empty!")
            return False
        
        print("\n" + "-"*60)
        print("Configuration Summary:")
        print("-"*60)
        print(f"Account: {account}")
        print(f"Password: {'*' * len(password)}")
        print(f"Server: {server}")
        print("-"*60 + "\n")
        
        confirm = input("Is this correct? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Setup cancelled.")
            return False
        
        # Load existing config
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Add MT5 section
        if "pipeline" not in config:
            config["pipeline"] = {}
        if "data_provider" not in config["pipeline"]:
            config["pipeline"]["data_provider"] = {}
        if "config" not in config["pipeline"]["data_provider"]:
            config["pipeline"]["data_provider"]["config"] = {}
        
        config["pipeline"]["data_provider"]["config"]["login"] = account
        config["pipeline"]["data_provider"]["config"]["password"] = password
        config["pipeline"]["data_provider"]["config"]["server"] = server
        
        # Save config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        print(f"✓ Configuration saved to {config_path}")
        print("\nNext step: Verify MT5 connection with:")
        print("  python diagnose_mt5.py")
        return True
        
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        return False


if __name__ == "__main__":
    success = setup_mt5_config()
    sys.exit(0 if success else 1)

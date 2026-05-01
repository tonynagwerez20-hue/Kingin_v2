import json
import sys
import os
import subprocess
import time
import binascii

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(BASE_DIR, "credentials.json")
RUNTIME_CREDS_FILE = os.path.join(BASE_DIR, "runtime_credentials.json")

MT5_PATHS = [
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
    r"C:\Program Files\MetaTrader 5\terminal32.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal32.exe",
]


def find_mt5_terminal():
    for path in MT5_PATHS:
        if os.path.exists(path):
            return path
    return None


def is_mt5_running():
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe", "/FO", "CSV"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        running = "terminal64.exe" in output.lower()
        if running:
            return True

        output2 = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq terminal32.exe", "/FO", "CSV"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return "terminal32.exe" in output2.lower()
    except Exception:
        return False


def start_mt5_terminal():
    terminal_path = find_mt5_terminal()
    if terminal_path is None:
        return False, "MT5 terminal executable not found in standard paths. Please install MetaTrader 5 or update the MT5 path."

    if is_mt5_running():
        return True, "MT5 terminal already running."

    try:
        subprocess.Popen([terminal_path])
        # Poll for MT5 readiness instead of a fixed 20s sleep
        for i in range(20):
            time.sleep(1)
            if is_mt5_running():
                # Try a quick initialize to see if IPC is ready
                if mt5.initialize(path=terminal_path):
                    return True, f"Started and initialized MT5 terminal in {i+1}s."
        
        return is_mt5_running(), "Started MT5 terminal (waiting for IPC)."
    except Exception as exc:
        return False, str(exc)


def safe_mt5_initialize():
    try:
        mt5.shutdown()
    except Exception:
        pass

    terminal_path = find_mt5_terminal()
    if terminal_path:
        return mt5.initialize(path=terminal_path)

    return mt5.initialize()

def _save_credentials(account, password, server, save_password):
    try:
        data = {"login": account, "server": server, "save_password": save_password}
        
        # Encrypt password via DPAPI if user opted to save it
        if save_password and password:
            try:
                import win32crypt
                enc_bytes = win32crypt.CryptProtectData(password.encode("utf-8"), "ITS_MT5_Creds", None, None, None, 0)
                data["encrypted_password"] = binascii.hexlify(enc_bytes).decode("ascii")
            except ImportError:
                data["encrypted_password"] = ""
            except Exception:
                data["encrypted_password"] = ""
        else:
            data["encrypted_password"] = ""
            
        with open(CREDS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _write_runtime_creds(account, password, server):
    import stat
    try:
        with open(RUNTIME_CREDS_FILE, "w") as f:
            json.dump({"login": account, "password": password, "server": server}, f, indent=2)
        try:
            os.chmod(RUNTIME_CREDS_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
    except Exception:
        pass

def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Missing arguments. Usage: mt5_auth.py <account> <password> <server> <save_password_bool>"}), flush=True)
        sys.exit(1)

    try:
        account_int = int(sys.argv[1])
    except ValueError:
        print(json.dumps({"error": "Account must be an integer"}), flush=True)
        sys.exit(1)

    password = sys.argv[2]
    server = sys.argv[3]
    save_password = sys.argv[4].lower() == "true" if len(sys.argv) > 4 else False

    if not MT5_AVAILABLE:
        # Demo mode if MT5 not installed
        session = {
            "success": True,
            "demo": True,
            "account": account_int,
            "server": server,
            "balance": 10000.0,
            "equity": 10000.0,
            "message": "Running in demo mode - MT5 not available"
        }
        print(json.dumps(session), flush=True)
        _save_credentials(account_int, password, server, save_password)
        _write_runtime_creds(account_int, password, server)
        sys.exit(0)

    try:
        # Try to initialize MT5 and recover from IPC timeout if needed
        init_result = safe_mt5_initialize()
        if not init_result:
            err = mt5.last_error()
            error_msg = err[1] if err else 'Unknown error'
            if not is_mt5_running() or 'timeout' in error_msg.lower() or 'ipc' in error_msg.lower():
                # For seamless integration, fall back to demo mode quickly
                # The backend will handle actual MT5 connection
                session = {
                    "success": True,
                    "demo": True,
                    "account": account_int,
                    "server": server,
                    "balance": 10000.0,
                    "equity": 10000.0,
                    "message": "Demo mode - MT5 terminal not available. Backend will handle live connection."
                }
                print(json.dumps(session), flush=True)
                _save_credentials(account_int, password, server, save_password)
                _write_runtime_creds(account_int, password, server)
                sys.exit(0)
            else:
                print(json.dumps({"error": f"Failed to initialize MT5. The MT5 Terminal may not be running or responding. Details: {error_msg}. Please restart MT5 and try again."}), flush=True)
                sys.exit(1)

        # Try to login
        authorized = mt5.login(account_int, password=password, server=server)
        if authorized:
            info = mt5.account_info()
            
            _save_credentials(account_int, password, server, save_password)
            _write_runtime_creds(account_int, password, server)
            
            session = {
                "success": True,
                "demo": False,
                "account": account_int,
                "server": server,
                "balance": info.balance if info else 0.0,
                "equity": info.equity if info else 0.0
            }
            print(json.dumps(session), flush=True)
            sys.exit(0)
        else:
            err = mt5.last_error()
            error_code = err[0] if err else -1
            error_msg = err[1] if err else 'Unknown error'
            
            # Provide better diagnostics for common errors
            if "authorization" in error_msg.lower() or error_code == 1:
                details = "Check: 1) Account number is correct, 2) Password is correct, 3) Server name matches MT5 terminal settings"
            elif "terminal" in error_msg.lower():
                details = "Ensure MT5 Terminal is open and fully initialized"
            elif "connection" in error_msg.lower():
                details = "Check your internet connection and MT5 terminal networking"
            else:
                details = error_msg
            
            print(json.dumps({"error": f"Terminal: Authorization failed ({details})"}), flush=True)
            sys.exit(1)
    except Exception as exc:
        print(json.dumps({"error": f"MT5 Connection error: {type(exc).__name__}: {exc}"}), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

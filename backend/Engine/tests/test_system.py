"""
Hedge Trading System - Comprehensive Test Suite
Tests all system components, integrations, and data flows.
"""
import sys
import time
import sqlite3
import requests
from pathlib import Path
import subprocess
import socket

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Test results tracking
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.tests = []
    
    def add_pass(self, test_name, message=""):
        self.passed += 1
        self.tests.append(("PASS", test_name, message))
        print(f"✓ PASS: {test_name}")
        if message:
            print(f"  → {message}")
    
    def add_fail(self, test_name, message=""):
        self.failed += 1
        self.tests.append(("FAIL", test_name, message))
        print(f"✗ FAIL: {test_name}")
        if message:
            print(f"  → {message}")
    
    def add_warning(self, test_name, message=""):
        self.warnings += 1
        self.tests.append(("WARN", test_name, message))
        print(f"⚠ WARN: {test_name}")
        if message:
            print(f"  → {message}")
    
    def print_summary(self):
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.passed + self.failed + self.warnings}")
        print(f"✓ Passed: {self.passed}")
        print(f"✗ Failed: {self.failed}")
        print(f"⚠ Warnings: {self.warnings}")
        print("="*60)
        
        if self.failed == 0:
            print("\n🎉 All critical tests passed!")
            return True
        else:
            print(f"\n❌ {self.failed} test(s) failed. Please review.")
            return False

results = TestResults()

def test_file_structure():
    """Test that all required files and directories exist."""
    print("\n" + "="*60)
    print("1. FILE STRUCTURE TESTS")
    print("="*60)
    
    required_files = [
        "Engine/main_loop.py",
        "Engine/bridge.py",
        "data feed/server.py",
        "data feed/dispatcher.py",
        "storage/hedge_db.py",
        "dashboard/dashboard.py",
        "dashboard/plot_pnl.py",
        "dashboard/view_trades.py",
        "start_system.py",
        "supervisor.py",
        "requirements.txt",
        "README.md"
    ]
    
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            results.add_pass(f"File exists: {file_path}")
        else:
            results.add_fail(f"File missing: {file_path}")
    
    # Check directories
    required_dirs = ["Engine", "data feed", "storage", "dashboard", "support", "data"]
    for dir_path in required_dirs:
        full_path = PROJECT_ROOT / dir_path
        if full_path.exists() and full_path.is_dir():
            results.add_pass(f"Directory exists: {dir_path}")
        else:
            results.add_fail(f"Directory missing: {dir_path}")

def test_python_dependencies():
    """Test that all required Python packages are installed."""
    print("\n" + "="*60)
    print("2. PYTHON DEPENDENCIES TESTS")
    print("="*60)
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "websockets",
        "pandas",
        "aiohttp",
        "zmq",
        "matplotlib",
        "streamlit",
        "sqlite3"  # Built-in, but check anyway
    ]
    
    for package in required_packages:
        try:
            if package == "zmq":
                __import__("zmq")
            else:
                __import__(package)
            results.add_pass(f"Package installed: {package}")
        except ImportError:
            results.add_fail(f"Package missing: {package}", "Run: pip install -r requirements.txt")

def test_database():
    """Test database connectivity and schema."""
    print("\n" + "="*60)
    print("3. DATABASE TESTS")
    print("="*60)
    
    db_path = PROJECT_ROOT / "data" / "hedge.db"
    
    if not db_path.exists():
        results.add_warning("Database file not found", f"Expected at: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ["candles", "trades", "buffers", "system_state", "aggregations"]
        for table in required_tables:
            if table in tables:
                results.add_pass(f"Table exists: {table}")
                
                # Check row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                results.add_pass(f"Table {table} has {count} rows")
            else:
                results.add_fail(f"Table missing: {table}")
        
        conn.close()
        
    except Exception as e:
        results.add_fail("Database connection failed", str(e))

def test_imports():
    """Test that all custom modules can be imported."""
    print("\n" + "="*60)
    print("4. MODULE IMPORT TESTS")
    print("="*60)
    
    # Add project root to path
    sys.path.insert(0, str(PROJECT_ROOT))
    
    modules_to_test = [
        ("storage.hedge_db", "HedgeDB"),
        ("Engine.bridge", "Bridge"),
    ]
    
    for module_path, class_name in modules_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)
            results.add_pass(f"Import successful: {module_path}.{class_name}")
        except Exception as e:
            results.add_fail(f"Import failed: {module_path}.{class_name}", str(e))

def test_port_availability():
    """Test that required ports are available."""
    print("\n" + "="*60)
    print("5. PORT AVAILABILITY TESTS")
    print("="*60)
    
    ports = {
        8000: "Data Feed Server (FastAPI)",
        5555: "ZMQ Bridge",
        8501: "Streamlit Dashboard"
    }
    
    for port, service in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result != 0:
            results.add_pass(f"Port {port} available ({service})")
        else:
            results.add_warning(
                f"Port {port} in use ({service})",
                "May indicate service is already running"
            )

def test_api_endpoints():
    """Test Data Feed Server API endpoints (if running)."""
    print("\n" + "="*60)
    print("6. API ENDPOINT TESTS (Optional)")
    print("="*60)
    
    base_url = "http://localhost:8000"
    
    # Check if server is running
    try:
        response = requests.get(f"{base_url}/docs", timeout=2)
        if response.status_code == 200:
            results.add_pass("Data Feed Server is running")
            
            # Test endpoints
            endpoints = ["/ohlc?tf=H1&limit=10", "/delta?tf=M5&limit=4"]
            for endpoint in endpoints:
                try:
                    resp = requests.get(f"{base_url}{endpoint}", timeout=2)
                    if resp.status_code == 200:
                        results.add_pass(f"API endpoint working: {endpoint}")
                    else:
                        results.add_warning(f"API endpoint returned {resp.status_code}: {endpoint}")
                except Exception as e:
                    results.add_warning(f"API endpoint error: {endpoint}", str(e))
        else:
            results.add_warning("Data Feed Server not responding correctly")
    except requests.exceptions.RequestException:
        results.add_warning(
            "Data Feed Server not running",
            "Start with: python 'data feed/server.py'"
        )

def test_dashboard_scripts():
    """Test dashboard scripts can be imported."""
    print("\n" + "="*60)
    print("7. DASHBOARD SCRIPT TESTS")
    print("="*60)
    
    scripts = [
        "dashboard/plot_pnl.py",
        "dashboard/view_trades.py",
        "dashboard/dashboard.py"
    ]
    
    for script in scripts:
        script_path = PROJECT_ROOT / script
        if script_path.exists():
            # Try to compile the script
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), script_path, 'exec')
                results.add_pass(f"Script syntax valid: {script}")
            except SyntaxError as e:
                results.add_fail(f"Script syntax error: {script}", str(e))
        else:
            results.add_fail(f"Script not found: {script}")

def test_configuration():
    """Test configuration files and settings."""
    print("\n" + "="*60)
    print("8. CONFIGURATION TESTS")
    print("="*60)
    
    # Check requirements.txt
    req_file = PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        with open(req_file, 'r') as f:
            packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        results.add_pass(f"requirements.txt found ({len(packages)} packages)")
    else:
        results.add_fail("requirements.txt not found")
    
    # Check README
    readme = PROJECT_ROOT / "README.md"
    if readme.exists():
        results.add_pass("README.md found")
    else:
        results.add_fail("README.md not found")

def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║      HEDGE TRADING SYSTEM - TEST SUITE                   ║
    ║      Comprehensive system validation                      ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Run all tests
    test_file_structure()
    test_python_dependencies()
    test_database()
    test_imports()
    test_port_availability()
    test_api_endpoints()
    test_dashboard_scripts()
    test_configuration()
    
    # Print summary
    success = results.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

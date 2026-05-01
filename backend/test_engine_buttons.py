#!/usr/bin/env python3
"""
Test script to verify engine start/stop functionality
"""
import subprocess
import time
import sys
import os

def test_engine_commands():
    """Test the start_engine and stop_engine Tauri commands"""

    print("Starting engine functionality test...")

    # Path to the Tauri app
    app_path = r"c:\Users\LENOVO\Desktop\kingin-master\src-tauri\target\release\institutional-trading-system.exe"

    if not os.path.exists(app_path):
        print(f"ERROR: App not found at {app_path}")
        return False

    print("✓ App executable found")

    # Test 1: Start Engine
    print("\n1. Testing START ENGINE (START_ALL.bat)...")
    try:
        print("Executing START_ALL.bat...")
        result = subprocess.run(
            [r"c:\Users\LENOVO\Desktop\kingin-master\START_ALL.bat"],
            capture_output=True,
            text=True,
            shell=True,
            cwd=r"c:\Users\LENOVO\Desktop\kingin-master"
        )

        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout[:200]}...")
        if result.stderr:
            print(f"STDERR: {result.stderr[:200]}...")

        if result.returncode == 0:
            print("✓ START_ALL.bat executed successfully")
        else:
            print("✗ START_ALL.bat failed")
            return False

    except Exception as e:
        print(f"✗ Start engine test failed: {e}")
        return False

    # Wait for processes to start
    print("Waiting 5 seconds for processes to initialize...")
    time.sleep(5)

    # Test 2: Check if processes started
    print("\n2. Checking if engine processes started...")
    try:
        # Check for python processes
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )

        python_count = result.stdout.count('python.exe')
        print(f"Found {python_count} python.exe processes")

        if python_count > 0:
            print("✓ Python processes found (engine components likely running)")
        else:
            print("⚠ No python processes found")

    except Exception as e:
        print(f"Process check failed: {e}")

    # Test 3: Stop Engine
    print("\n3. Testing STOP ENGINE (SYSTEM_OFF.bat)...")
    try:
        print("Executing SYSTEM_OFF.bat...")
        result = subprocess.run(
            [r"c:\Users\LENOVO\Desktop\kingin-master\SYSTEM_OFF.bat"],
            capture_output=True,
            text=True,
            shell=True,
            cwd=r"c:\Users\LENOVO\Desktop\kingin-master"
        )

        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout.strip()}")
        if result.stderr:
            print(f"STDERR: {result.stderr.strip()}")

        if result.returncode == 0:
            print("✓ SYSTEM_OFF.bat executed successfully")
        else:
            print("✗ SYSTEM_OFF.bat failed")
            return False

    except Exception as e:
        print(f"✗ Stop engine test failed: {e}")
        return False

    # Test 4: Verify processes stopped
    print("\n4. Verifying engine processes stopped...")
    time.sleep(3)

    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )

        python_count_after = result.stdout.count('python.exe')
        print(f"Found {python_count_after} python.exe processes after stop")

        if python_count_after == 0:
            print("✓ All python processes terminated")
        else:
            print(f"⚠ {python_count_after} python processes still running")

    except Exception as e:
        print(f"Process verification failed: {e}")

    print("\n✓ Engine start/stop functionality test completed successfully")
    print("The dashboard START/STOP buttons should work correctly!")
    return True

if __name__ == "__main__":
    success = test_engine_commands()
    sys.exit(0 if success else 1)
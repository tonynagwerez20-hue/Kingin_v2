import requests
import time
import subprocess
import sys
import os

PORT = 8088
URL = f"http://127.0.0.1:{PORT}/api/system/status"

def test():
    print(f"--- KingIn Diagnostic Tool ---")
    print(f"Target URL: {URL}")
    
    try:
        print(f"Checking if port {PORT} is already in use...")
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            in_use = s.connect_ex(('127.0.0.1', PORT)) == 0
            if in_use:
                print(f"[!] Port {PORT} is ALREADY IN USE by another process.")
            else:
                print(f"[OK] Port {PORT} is free.")
    except Exception as e:
        print(f"[?] Could not check port status: {e}")

    print("\nAttempting to ping FastAPI...")
    try:
        response = requests.get(URL, timeout=5)
        print(f"[SUCCESS] Received response from FastAPI:")
        print(f"Status Code: {response.status_code}")
        print(f"Body: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] Connection Error: Is the backend server running?")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

    print("\nDiagnostic complete.")

if __name__ == "__main__":
    test()

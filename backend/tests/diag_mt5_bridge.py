import zmq
import json
import time
import sys

def diag_mt5_bridge():
    print("=== MT5 Bridge Diagnostic Tool ===")
    context = zmq.Context()
    
    # Check REQ socket for commands (Balance, Positions, History)
    req_port = 5557
    print(f"Connecting to REQ Port: {req_port}...")
    req_socket = context.socket(zmq.REQ)
    req_socket.connect(f"tcp://localhost:{req_port}")
    req_socket.setsockopt(zmq.RCVTIMEO, 5000)
    
    # 1. Heartbeat Test
    print("\n[1] Testing Heartbeat (PING)...")
    try:
        req_socket.send_string("PING")
        res = req_socket.recv_string()
        if res == "PONG":
            print("  SUCCESS: Received PONG from MT5 EA")
        else:
            print(f"  WARNING: Received unexpected response: {res}")
    except zmq.Again:
        print("  FAILURE: Request timed out. Is the EA running in MT5?")
    except Exception as e:
        print(f"  ERROR: {e}")

    # 2. Account Balance Test
    print("\n[2] Testing Account Balance Query...")
    try:
        req_socket.send_json({"type": "GET_BALANCE"})
        res = req_socket.recv_json()
        if res.get("status") == "SUCCESS":
            print(f"  SUCCESS: Balance = ${res.get('balance'):.2f}")
        else:
            print(f"  FAILURE: EA returned error: {res.get('error')}")
    except zmq.Again:
        print("  FAILURE: Timeout waiting for balance.")
    except Exception as e:
        print(f"  ERROR: {e}")

    # 3. Position Query Test
    print("\n[3] Testing Open Positions Query...")
    try:
        req_socket.send_json({"type": "GET_POSITIONS"})
        res = req_socket.recv_json()
        if res.get("status") == "SUCCESS":
            positions = res.get("positions", [])
            print(f"  SUCCESS: Found {len(positions)} open positions")
            for p in positions:
                print(f"    - Ticket {p.get('ticket')}: {p.get('type')} {p.get('volume')} @ {p.get('price_open')}")
        else:
            print(f"  FAILURE: EA returned error: {res.get('error')}")
    except zmq.Again:
        print("  FAILURE: Timeout waiting for positions.")
    except Exception as e:
        print(f"  ERROR: {e}")

    # 4. Symbol Mapping Hint
    print("\n[4] Symbol Mapping Verification:")
    try:
        from support.env_loader import get_env
        symbol = get_env("TRADING_SYMBOL", "NOT_SET")
        print(f"  Configured TRADING_SYMBOL: {symbol}")
        print("  Note: If this doesn't match MT5 exactly (e.g., [M] suffix), orders will fail.")
    except:
        print("  Could not load .env configuration.")

    print("\n=== End of Diagnostic ===")
    req_socket.close()
    context.term()

if __name__ == "__main__":
    diag_mt5_bridge()

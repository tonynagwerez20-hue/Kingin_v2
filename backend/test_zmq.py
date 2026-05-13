import zmq
import time
import json

def test_mt5_bridge():
    context = zmq.Context()
    
    # Test Req/Rep (Port 5557)
    print("--- MT5 ZMQ Bridge Diagnostic ---")
    print("Connecting to Requester (Port 5557)...")
    requester = context.socket(zmq.REQ)
    requester.connect("tcp://127.0.0.1:5557")
    requester.setsockopt(zmq.RCVTIMEO, 5000) # 5s timeout
    
    try:
        print("Sending Ping to MT5 EA...")
        requester.send_string(json.dumps({"action": "PING", "symbol": "XAUUSD"}))
        response = requester.recv_string()
        print(f"[OK] MT5 Response received: {response}")
    except zmq.Again:
        print("[FAIL] MT5 EA timed out. Possible reasons:")
        print("  - EA is not attached to a chart.")
        print("  - DLL imports are not enabled in EA settings.")
        print("  - Firewall is blocking port 5557.")
    except Exception as e:
        print(f"[ERROR] ZMQ Error: {e}")
    finally:
        requester.close()
        context.term()

if __name__ == "__main__":
    test_mt5_bridge()

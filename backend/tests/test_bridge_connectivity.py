import zmq
import json
import time

def test_bridge():
    context = zmq.Context()
    req_socket = context.socket(zmq.REQ)
    req_socket.connect("tcp://localhost:5557")
    req_socket.setsockopt(zmq.RCVTIMEO, 2000)
    
    print("Testing Bridge Connectivity...")
    
    # 1. PING
    try:
        print("Sending PING...")
        req_socket.send_string("PING")
        res = req_socket.recv_string()
        print(f"PING Response: {res}")
    except Exception as e:
        print(f"PING Failed: {e}")

    # 2. GET_POSITIONS
    try:
        print("\nSending GET_POSITIONS...")
        req_socket.send_json({"type": "GET_POSITIONS"})
        res = req_socket.recv_json()
        print(f"GET_POSITIONS Response: {json.dumps(res, indent=2)}")
    except Exception as e:
        print(f"GET_POSITIONS Failed: {e}")

    # 3. GET_HISTORY
    try:
        print("\nSending GET_HISTORY (days=1)...")
        req_socket.send_json({"type": "GET_HISTORY", "days": 1})
        res = req_socket.recv_json()
        print(f"GET_HISTORY Response: {json.dumps(res, indent=2)}")
    except Exception as e:
        print(f"GET_HISTORY Failed: {e}")

    req_socket.close()
    context.term()

if __name__ == "__main__":
    test_bridge()

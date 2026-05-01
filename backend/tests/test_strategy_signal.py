import zmq
import json
import time

# ZMQ Configuration
ZMQ_HOST = "localhost"
ZMQ_PORT = 5555
ZMQ_TOPIC = "SIGNAL"

def send_mock_signal():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://*:{ZMQ_PORT}")
    
    print(f"[Simulator] Publisher bound to port {ZMQ_PORT}")
    print("[Simulator] Waiting 2s for MT5 to connect...")
    time.sleep(2)

    # Reality Check: Real-time Gold Price (Jan 9, 2026) approx $4473.17
    current_price = 4473.17
    
    # Mock Signal Data: Simulation of a Bearish Breakdown
    # Strategy: H1 Bias is BEARISH, M15 is in a Supply Zone, M5 Delta just flipped Negative.
    mock_signal = {
        "action": "SHORT",
        "symbol": "XAUUSD",
        "price": current_price,
        "sl": current_price + 2.50, # 25 pip stop
        "lots": 0.10,
        "bias": "BEARISH",
        "timestamp": int(time.time()),
        "desc": "MOCK TEST: H1 Bearish + M15 Supply + M5 Delta Flip"
    }

    message = f"{ZMQ_TOPIC} {json.dumps(mock_signal)}"
    
    print(f"[Simulator] Sending signal: {mock_signal['action']} at {mock_signal['price']}")
    socket.send_string(message)
    
    print("[Simulator] Signal broadcasted. Check MT5 Experts Tab.")
    time.sleep(1)
    socket.close()
    context.term()

if __name__ == "__main__":
    try:
        send_mock_signal()
    except Exception as e:
        print(f"[Error] Simulation failed: {e}")

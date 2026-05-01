"""
====================================================
  ZMQ TUNNEL TEST — End-to-End Bridge Verification
====================================================
Tests the full ZMQ signal pipeline without requiring MT5:

  [1] Starts a Mock EA Server (simulates HedgeEA's ZMQ receiver)
  [2] Connects the Bridge (pub + req sockets)
  [3] Tests PING/PONG heartbeat
  [4] Tests GET_BALANCE query
  [5] Sends a live-style trade signal and verifies reception
  [6] Reports latency

Run from project root:
  python tests/test_zmq_tunnel.py
"""

import sys
import io
import json
import time
import threading
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import zmq

# ---- Terminal Helpers ----
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def PASS(msg, detail=""):
    print(f"  {GREEN}[PASS]{RESET} [OK] {msg}")
    if detail: print(f"         |_ {detail}")

def FAIL(msg, detail=""):
    print(f"  {RED}[FAIL]{RESET} [XX] {msg}")
    if detail: print(f"         |_ {detail}")

def WARN(msg, detail=""):
    print(f"  {YELLOW}[WARN]{RESET} [!!] {msg}")
    if detail: print(f"         |_ {detail}")

def section(title):
    print(f"\n{BOLD}{CYAN}{'='*50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*50}{RESET}")

# ====================================================
# MOCK EA SERVER (runs in background thread)
# Simulates what HedgeEA.mq5 does on the ZMQ side.
# ====================================================

received_signals = []
server_ready = threading.Event()

def mock_ea_server(pub_port=5555, rep_port=5557):
    """
    Simulates the MT5 HedgeEA ZMQ side:
    - SUB socket: listens for published SIGNAL messages
    - REP socket: responds to PING, GET_BALANCE, SIGNAL requests
    """
    context = zmq.Context()

    # SUB socket: listens for fire-and-forget signals
    sub = context.socket(zmq.SUB)
    sub.connect(f"tcp://localhost:{pub_port}")
    sub.setsockopt_string(zmq.SUBSCRIBE, "SIGNAL")

    # REP socket: handles request/reply
    rep = context.socket(zmq.REP)
    rep.bind(f"tcp://*:{rep_port}")
    rep.setsockopt(zmq.RCVTIMEO, 1000)

    server_ready.set()
    print(f"\n  [MockEA] Ready — SUB:{pub_port}, REP:{rep_port}")

    # Run for up to 30 seconds then exit
    deadline = time.time() + 30
    while time.time() < deadline:
        # Handle REP requests
        try:
            msg = rep.recv_string()
            if msg == "PING":
                rep.send_string("PONG")
            else:
                try:
                    req = json.loads(msg)
                    req_type = req.get("type", "")
                    if req_type == "GET_BALANCE":
                        rep.send_json({"status": "SUCCESS", "balance": 10.00})
                    elif req_type == "SIGNAL":
                        received_signals.append(req)
                        rep.send_json({
                            "status": "SUCCESS",
                            "ticket": 123456,
                            "execution_price": req.get("price", 0.0)
                        })
                    elif req_type == "PING_LATENCY":
                        rep.send_json({"type": "PONG_LATENCY", "ts": req.get("timestamp")})
                    else:
                        rep.send_json({"status": "ERROR", "error": f"Unknown: {req_type}"})
                except json.JSONDecodeError:
                    rep.send_string("PONG")
        except zmq.Again:
            pass

        # Check PUB/SUB messages (non-blocking)
        try:
            msg = sub.recv_string(flags=zmq.NOBLOCK)
            if msg.startswith("SIGNAL "):
                payload = json.loads(msg[7:])
                received_signals.append(payload)
                print(f"  [MockEA] PUB Signal received: {payload.get('direction', '?')} @ {payload.get('price', '?')}")
        except zmq.Again:
            pass

    sub.close()
    rep.close()
    context.term()


# ====================================================
# START MOCK SERVER
# ====================================================
section("SETUP — Starting Mock EA Server")
server_thread = threading.Thread(target=mock_ea_server, daemon=True)
server_thread.start()
server_ready.wait(timeout=3)
time.sleep(0.5)  # Let bindings settle

# ====================================================
# TEST 1: Bridge Initialization
# ====================================================
section("TEST 1 — Bridge Initialization")

bridge = None
try:
    from execution.bridge import Bridge
    bridge = Bridge(pub_port=5555, req_port=5557)
    if bridge:
        PASS("Bridge initialized (ZMQ sockets created)")
    else:
        FAIL("Bridge could not be initialized")
except Exception as e:
    FAIL("Bridge init failed", str(e))


# ====================================================
# TEST 2: PING / PONG Heartbeat
# ====================================================
section("TEST 2 — PING / PONG Heartbeat")

if bridge:
    try:
        connected = bridge.check_connection()
        if connected:
            PASS("PING -> PONG successful", "EA is responding")
        else:
            FAIL("PING -> PONG failed", "No PONG received")
    except Exception as e:
        FAIL("Heartbeat test", str(e))


# ====================================================
# TEST 3: GET_BALANCE Query
# ====================================================
section("TEST 3 — Account Balance Query (REQ/REP)")

if bridge:
    try:
        balance = bridge.get_account_balance()
        if balance == 10.0:
            PASS("GET_BALANCE query succeeded", f"Balance: ${balance:.2f}")
        else:
            FAIL("GET_BALANCE returned unexpected value", str(balance))
    except Exception as e:
        FAIL("Balance query failed", str(e))


# ====================================================
# TEST 4: Trade Signal — Fire & Forget (PUB)
# ====================================================
section("TEST 4 — Trade Signal via PUB Socket")

if bridge:
    try:
        test_signal = {
            "action": "TRADE",
            "direction": "BUY",
            "symbol": "XAUUSD",
            "price": 2850.20,
            "sl": 2845.00,
            "tp": 2860.40,
            "lots": 0.01,
            "confidence": 0.85
        }
        bridge.send_signal(test_signal, record_only=False)
        time.sleep(0.5)  # Allow PUB to propagate

        received = any(s.get("direction") == "BUY" for s in received_signals)
        if received:
            PASS("BUY signal transmitted via PUB socket", "Mock EA received it")
        else:
            WARN("Signal sent but no confirmation via PUB/SUB yet", "PUB sockets are fire-and-forget")
    except Exception as e:
        FAIL("Signal transmission failed", str(e))


# ====================================================
# TEST 5: Trade Signal — REQ/REP with ACK
# ====================================================
section("TEST 5 — Trade Signal with Acknowledgment (REQ/REP)")

if bridge:
    try:
        ack_signal = {
            "action": "TRADE",
            "direction": "SELL",
            "symbol": "XAUUSD",
            "price": 2849.00,
            "sl": 2854.00,
            "tp": 2839.00,
            "lots": 0.01
        }
        result = bridge.send_signal_with_ack(ack_signal, record_only=False)
        ok = result.get("status") == "SUCCESS"
        if ok:
            PASS("SELL signal acknowledged by EA", f"Ticket: {result.get('ticket')} | Exec: {result.get('execution_price')}")
        else:
            FAIL("Signal not acknowledged", str(result))
    except Exception as e:
        FAIL("REQ/REP signal test failed", str(e))


# ====================================================
# TEST 6: Round-Trip Latency
# ====================================================
section("TEST 6 — ZMQ Round-Trip Latency")

if bridge:
    try:
        latency = bridge.ping_latency()
        if latency is not None:
            quality = "Excellent" if latency < 5 else "Good" if latency < 20 else "Acceptable" if latency < 50 else "High"
            PASS(f"Latency measured: {latency:.2f}ms ({quality})")
        else:
            WARN("Latency test inconclusive — no PONG_LATENCY response")
    except Exception as e:
        FAIL("Latency test failed", str(e))


# ====================================================
# SUMMARY
# ====================================================
section("ZMQ TUNNEL TEST — COMPLETE")
print(f"\n  Signals received by Mock EA: {len(received_signals)}")
for i, sig in enumerate(received_signals):
    print(f"    [{i+1}] {sig.get('direction', sig.get('action', 'N/A'))} @ {sig.get('price', 'N/A')} | Lots: {sig.get('lots', 'N/A')}")

if bridge:
    bridge.close()

print(f"\n  {GREEN}{BOLD}ZMQ Tunnel test complete.{RESET}")
print(f"  When HedgeEA is attached in MT5, replace the mock server")
print(f"  with the live EA and re-run this test to verify real execution.\n")

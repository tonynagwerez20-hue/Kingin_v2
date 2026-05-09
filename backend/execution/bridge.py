import zmq
import json
import time
from typing import Dict, Optional, List
from support.backtest.signal_recorder import recorder

class Bridge:
    """
    Enhanced ZeroMQ Bridge to communicate with MetaTrader 5 EA.
    Supports both fire-and-forget signals (PUB) and request-reply (REQ) for acknowledgments.
    Can also use a direct MT5 library session for high-fidelity data syncing.
    """
    def __init__(self, pub_port: int = 5555, req_port: int = 5557, mt5_session: Optional[Dict] = None):
        self.mt5_session = mt5_session
        self.context = zmq.Context()
        
        # PUB socket for fire-and-forget signals (backward compatible)
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://*:{pub_port}")
        print(f"[Bridge] ZMQ Publisher bound to port {pub_port}")
        
        # REQ socket for acknowledgments and queries
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.connect(f"tcp://localhost:{req_port}")
        self.req_socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5 second timeout
        self.req_socket.setsockopt(zmq.SNDTIMEO, 5000)
        print(f"[Bridge] ZMQ Requester connected to port {req_port}")
        
        self.connected = False
        
        # Symbol Mapping (Sierra XAUUSD -> Broker XAUUSD[M])
        try:
            from support.env_loader import get_env
            self.trading_symbol = get_env("TRADING_SYMBOL", None)
        except ImportError:
            self.trading_symbol = None
            
        self._test_connection()
    
    def _test_connection(self):
        """Test connection to MT5 EA via heartbeat."""
        try:
            response = self._send_request("PING")
            if response == "PONG":
                self.connected = True
                print("[Bridge] MT5 EA connection verified")
            else:
                print(f"[Bridge] Unexpected heartbeat response: {response}")
        except Exception as e:
            print(f"[Bridge] MT5 EA not responding: {e}")
            self.connected = False
    
    def _send_request(self, message: str, timeout: int = 5) -> Optional[str]:
        """Send a request and wait for response."""
        try:
            self.req_socket.send_string(message)
            response = self.req_socket.recv_string()
            return response
        except zmq.Again:
            print(f"[Bridge] Request timeout after {timeout}s")
            return None
        except Exception as e:
            print(f"[Bridge] Request error: {e}")
            return None
    
    def send_signal(self, signal: dict, record_only: bool = False):
        """
        Sends a JSON-encoded signal over ZMQ (fire-and-forget).
        Backward compatible with existing EA.
        """
        # 1. Record the signal for backtesting/auditing
        recorder.record(signal)
        
        if record_only:
            print(f"[Bridge] Signal RECORDED (Offline Mode): {signal.get('action')}")
            return

        # Apply Symbol Mapping if defined
        if self.trading_symbol and signal.get("symbol") == "XAUUSD":
            signal["symbol"] = self.trading_symbol
            
        # [Autofix] Inject timestamp if missing (Crucial for EA expiration check)
        if "timestamp" not in signal:
            signal["timestamp"] = int(time.time())
            
        message = json.dumps(signal)
        self.pub_socket.send_string(f"SIGNAL {message}")
        print(f"[Bridge] Signal sent: {message}")
    
    def send_signal_with_ack(self, signal: dict, timeout: int = 5, max_retries: int = 3, record_only: bool = False) -> Dict:
        """
        Send signal and wait for acknowledgment from MT5 EA.
        Implements retry logic with exponential backoff.
        
        Returns:
            Dict with status, ticket, execution_price, etc.
        """
        # 1. Record the signal for backtesting/auditing
        recorder.record(signal)

        if record_only:
             print(f"[Bridge] Signal RECORDED (Offline Mode): {signal.get('action')}")
             return {"status": "SUCCESS", "mode": "OFFLINE_RECORD"}
        # Apply Symbol Mapping if defined
        if self.trading_symbol and signal.get("symbol") == "XAUUSD":
            signal["symbol"] = self.trading_symbol

        for attempt in range(max_retries):
            try:
                # Send signal via REQ socket
                request = {
                    "type": "SIGNAL",
                    **signal
                }
                self.req_socket.send_json(request)
                
                # Wait for acknowledgment
                ack = self.req_socket.recv_json()
                
                if ack.get("status") == "SUCCESS":
                    print(f"[Bridge] Signal acknowledged: Ticket {ack.get('ticket')}")
                    return ack
                else:
                    print(f"[Bridge] Signal failed: {ack.get('error', 'Unknown error')}")
                    return ack
                    
            except zmq.Again:
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                print(f"[Bridge] Timeout on attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                
                # Recreate socket to clear state
                self.req_socket.close()
                self.req_socket = self.context.socket(zmq.REQ)
                self.req_socket.connect(f"tcp://localhost:5557")
                self.req_socket.setsockopt(zmq.RCVTIMEO, timeout * 1000)
                self.req_socket.setsockopt(zmq.SNDTIMEO, timeout * 1000)
                
            except Exception as e:
                print(f"[Bridge] Error sending signal with ack: {e}")
                return {"status": "ERROR", "error": str(e)}
        
        return {"status": "TIMEOUT", "error": "Max retries exceeded"}
    
    def _request_json(self, request: Dict) -> Optional[Dict]:
        """
        Unified helper for JSON REQ/REP with state recovery.
        Ensures the socket is in a valid state even after failures.
        """
        try:
            # Send request
            self.req_socket.send_json(request)
            
            # Wait for response
            response = self.req_socket.recv_json()
            return response
            
        except zmq.Again:
            print(f"[Bridge] Timeout on request type: {request.get('type')}")
        except Exception as e:
            print(f"[Bridge] Request error ({request.get('type')}): {e}")
            
        # If we reach here, the REQ/REP state is broken.
        # We MUST recreate the socket to recover.
        self._reset_req_socket()
        return None

    def _reset_req_socket(self):
        """Recreate the REQ socket to clear error states."""
        try:
            self.req_socket.close(linger=0)
            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.connect(f"tcp://localhost:5557")
            self.req_socket.setsockopt(zmq.RCVTIMEO, 5000)
            self.req_socket.setsockopt(zmq.SNDTIMEO, 5000)
            print("[Bridge] ZMQ REQ socket reset performed")
        except Exception as e:
            print(f"[Bridge] Failed to reset REQ socket: {e}")

    def get_account_balance(self) -> Optional[float]:
        """Query MT5 for current account balance. Favors direct MT5 session."""
        if self.mt5_session:
            try:
                import MetaTrader5 as mt5
                info = mt5.account_info()
                if info:
                    return info.balance
            except:
                pass
        
        response = self._request_json({"type": "GET_BALANCE"})
        if response and response.get("status") == "SUCCESS":
            balance = response.get("balance", 0.0)
            print(f"[Bridge] Account balance (ZMQ): ${balance:.2f}")
            return balance
        return None

    def get_account_equity(self) -> Optional[float]:
        """Query MT5 for current account equity. Favors direct MT5 session."""
        if self.mt5_session:
            try:
                import MetaTrader5 as mt5
                info = mt5.account_info()
                if info:
                    return info.equity
            except:
                pass
        
        response = self._request_json({"type": "GET_EQUITY"})
        if response and response.get("status") == "SUCCESS":
            return response.get("equity", 0.0)
        return None

    def get_open_positions(self) -> List[Dict]:
        """Query MT5 for currently open positions. Favors direct MT5 session."""
        if self.mt5_session:
            try:
                import MetaTrader5 as mt5
                pos = mt5.positions_get()
                if pos is not None:
                    return [
                        {
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "type": "BUY" if p.type == 0 else "SELL",
                            "lots": p.volume,
                            "open_price": p.price_open,
                            "current_price": p.price_current,
                            "sl": p.sl,
                            "tp": p.tp,
                            "floating_pnl": p.profit,
                            "open_time": p.time
                        }
                        for p in pos
                    ]
            except:
                pass

        # Fallback to ZMQ
        response = self._request_json({"type": "GET_POSITIONS"})
        if response and response.get("status") == "SUCCESS":
            return response.get("positions", [])
        elif response and response.get("status") == "ERROR":
             print(f"[Bridge] EA Error on GET_POSITIONS: {response.get('error')}")
        return []

    def ping_latency(self) -> Optional[float]:
        """Measure round-trip latency to MT5 EA in milliseconds."""
        try:
            start_time = time.time()
            request = {
                "type": "PING_LATENCY",
                "timestamp": int(start_time * 1000)
            }
            
            # Send ping request
            self.req_socket.send_json(request)
            
            # Wait for pong response
            response = self.req_socket.recv_json()
            end_time = time.time()
            
            if response and response.get("type") == "PONG_LATENCY":
                latency_ms = (end_time - start_time) * 1000
                return latency_ms
            else:
                return None
        except zmq.Again:
            print("[Bridge] Latency ping timeout")
            self._reset_req_socket()
            return None
        except Exception as e:
            print(f"[Bridge] Latency ping error: {e}")
            self._reset_req_socket()
            return None

    def get_market_spread(self) -> Optional[float]:
        """Query MT5 EA for current market spread in pips."""
        response = self._request_json({"type": "GET_SPREAD"})
        if response and response.get("status") == "SUCCESS":
            spread = response.get("spread", 1.5)
            print(f"[Bridge] Current spread: {spread} pips")
            return spread
        return None

    def get_trade_history(self, days: int = 7) -> List[Dict]:
        """Query MT5 EA for closed trade history."""
        # Using 'GET_HISTORY' as industry standard.
        response = self._request_json({"type": "GET_HISTORY", "days": days})
        if response and response.get("status") == "SUCCESS":
            return response.get("history", [])
        elif response and response.get("status") == "ERROR":
             print(f"[Bridge] EA Error on GET_HISTORY: {response.get('error')}")
        return []

    def check_connection(self) -> bool:
        """Check if MT5 EA is responding."""
        try:
            response = self._send_request("PING")
            self.connected = (response == "PONG")
            return self.connected
        except:
            self.connected = False
            return False
    
    def close(self):
        """Clean up sockets."""
        self.pub_socket.close()
        self.req_socket.close()
        self.context.term()
        print("[Bridge] ZMQ sockets closed")

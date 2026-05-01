import socket
import struct
import threading
import time
import queue
import json
import asyncio
from enum import Enum, auto
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional
import data_feed.dtc_protocol as dtc
from concurrent.futures import ThreadPoolExecutor
from config.settings import DTC_HOST, DTC_PORT_LIVE, DTC_PORT_HIST, DEFAULT_SYMBOLS

class DTCState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    LOGON_WAIT = auto()
    HIST_WAIT = auto()
    LIVE = auto()
    ERROR = auto()

class TimeframeEngine:
    """Manages real-time bar aggregation and persistence."""
    def __init__(self, symbol="XAUUSD"):
        self.symbol = symbol
        self.tf_seconds = {"M5": 300, "M15": 900, "H1": 3600}
        self.active_bars = {tf: {"open": 0, "high":0, "low":0, "close":0, "volume":0, "delta":0, "time":0, "_init": False} for tf in self.tf_seconds}
        self.lock = threading.Lock()

    def process_tick(self, price: float, volume: float, direction: int, timestamp: int = None):
        if timestamp is None: timestamp = int(time.time())
        with self.lock:
            for tf, bar in self.active_bars.items():
                interval = self.tf_seconds[tf]
                bar_start = (timestamp // interval) * interval
                
                if bar["_init"] and bar_start > bar["time"]:
                    self._close_bar(tf, bar)
                    bar.update({"open":price, "high":price, "low":price, "close":price, "volume":volume, "delta":volume*direction, "time":bar_start, "_init":True})
                elif not bar["_init"]:
                    bar.update({"open":price, "high":price, "low":price, "close":price, "volume":volume, "delta":volume*direction, "time":bar_start, "_init":True})
                else:
                    bar["high"] = max(bar["high"], price)
                    bar["low"] = min(bar["low"], price)
                    bar["close"] = price
                    bar["volume"] += volume
                    bar["delta"] += (volume * direction)
                
                self._sync_to_global(tf, bar)

    def _close_bar(self, tf, bar):
        print(f"[Engine] {tf} Closed: {bar['close']} @ {bar['time']}")
        try:
            from storage.hedge_db import HedgeDB
            db = HedgeDB()
            db.insert_candle(self.symbol, tf, bar["open"], bar["high"], bar["low"], bar["close"], bar["time"], bar["volume"])
            db.close()
        except: pass

    def _sync_to_global(self, tf, bar):
        try:
            from data_feed.dispatcher import ohlc_buffers, latest_tick
            
            # v3.9 Multi-Symbol Key (Default XAUUSD for backward compat if symbol matches)
            # Actually, standardizing on Symbol_TF for all?
            # Existing main_loop expects "M5" etc. for default symbol.
            # Let's check config.
            key = tf
            if self.symbol != "XAUUSD":
                key = f"{self.symbol}_{tf}"
            else:
                 # Ensure XAUUSD also populates the specific key
                 alt_key = f"{self.symbol}_{tf}"
                 if alt_key not in ohlc_buffers: ohlc_buffers[alt_key] = deque(maxlen=500)
                 self._update_buffer(ohlc_buffers[alt_key], bar)

            if key not in ohlc_buffers:
                ohlc_buffers[key] = deque(maxlen=500)
            
            self._update_buffer(ohlc_buffers[key], bar)
                
            # Update latest_tick for real-time dashboard (use M5 as primary)
            if tf == "M5" and self.symbol == "XAUUSD":
                latest_tick["price"] = bar["close"]
                latest_tick["timestamp"] = bar["time"]
                latest_tick["volume"] = bar["volume"]
                latest_tick["bid"] = bar["close"] - 0.75
                latest_tick["ask"] = bar["close"] + 0.75
        except Exception as e: 
            print(f"Sync error: {e}")

    def _update_buffer(self, buf, bar):
        data = {k:v for k,v in bar.items() if k != "_init"}
        if not buf or buf[-1]["time"] < bar["time"]: buf.append(data)
        else: buf[-1] = data


class DepthEngine:
    """Reconstructs Order Book (DOM) from DTC Updates"""
    def __init__(self, symbol):
        self.symbol = symbol
        self.bids = {} # Price -> Size
        self.asks = {}
        self.lock = threading.Lock()
        
    def update(self, price, size, side):
        # 1=Bid, 2=Ask
        with self.lock:
            book = self.bids if side == 1 else self.asks
            if size == 0:
                if price in book: del book[price]
            else:
                book[price] = size
                
    def get_snapshot(self):
        with self.lock:
            return {
                "bids": dict(sorted(self.bids.items(), reverse=True)[:10]),
                "asks": dict(sorted(self.asks.items())[:10])
            }

class DTCClient:
    def __init__(self, host=DTC_HOST, port_live=DTC_PORT_LIVE, port_hist=DTC_PORT_HIST, symbols=DEFAULT_SYMBOLS, skip_history=False):
        self.host, self.port_live, self.port_hist = host, port_live, port_hist
        self.symbols = symbols if isinstance(symbols, list) else [symbols]
        self.skip_history = skip_history
        
        self.sock_live = self.sock_hist = None
        self.running = False
        self.state = DTCState.DISCONNECTED
        self.live_logon = self.hist_logon = False
        self.msg_queue = queue.Queue()
        
        # ID Maps
        self.symbol_id_map = {i+1: s for i, s in enumerate(self.symbols)} # ID -> Symbol
        self.rev_symbol_id_map = {s: i+1 for i, s in enumerate(self.symbols)}
        
        # Engines
        self.engines = {s: TimeframeEngine(s) for s in self.symbols}
        self.depth_engines = {s: DepthEngine(s) for s in self.symbols}
        
        self.is_synced = True # v3.10: Default to True for Hybrid/CSV mode compatibility
        
        self.pending_hist_requests = set()
        self.request_map = {} # ReqID -> (Symbol, TF)
        self.one_hist_req = False 
        self.temp_historical_data = [] 
        self.last_live_hb = self.last_hist_hb = time.time()
        self.sock_lock = threading.RLock() # v3.2: Re-entrant lock prevents heartbeat deadlock
        self.is_downloading = False # Fix A: Track history download activity
        self.heartbeat_interval = 30 # v3.1 hardening: Request 30s interval for stability
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="DTC-Worker")
        
        # Initialize history queue once at construction
        self.hist_queue = deque([(1003, 3600), (1002, 900), (1001, 300)])
        self.pending_hist_requests = {1003, 1002, 1001}
        
        # v3.8: Hybrid Mode strict enforcement
        if self.skip_history:
            print("[DTC] Hybrid Mode Active: Clearing history queue to prevent download attempts.")
            self.hist_queue.clear()
            self.pending_hist_requests.clear()
            
        print(f"[DTC] Client Initialized. History Queue defined: {[ (r, i) for r, i in self.hist_queue ]}")

    def connect(self, host=DTC_HOST, port=None, is_live=True):
        """Connect to Sierra Chart DTC Server (Fixed to localhost for stability)"""
        if port is None:
            port = self.port_live if is_live else self.port_hist
        target_host = host
        target_port = port
        sock_name = "LIVE" if is_live else "HIST"

        try:
            print(f"[DTC] Connecting {sock_name} Port {target_port} on {target_host}...")
            sock = socket.create_connection((target_host, target_port), 20)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(15.0)

            with self.sock_lock:
                if is_live:
                    self.sock_live = sock
                else:
                    self.sock_hist = sock
            
            threading.Thread(target=self._receiver_loop, args=(sock, is_live), name=f"DTC-{sock_name}Recv", daemon=True).start()
            self._send_raw(dtc.LogonRequest(heartbeat_interval=self.heartbeat_interval).pack_json(), is_live)
            
            if not is_live:
                self.state = DTCState.CONNECTING # Revert v3.5: Wait for Logon Response
            return True
        except Exception as e:
            print(f"[DTC] Connection failed to {target_host}:{target_port} ({sock_name}): {e}")
            return False

    def start(self):
        self.running = True
        threading.Thread(target=self._connection_manager, name="DTC-ConnManager", daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, name="DTC-Heartbeat", daemon=True).start()
        threading.Thread(target=self._processor_loop, name="DTC-Processor", daemon=True).start()
        return True

    def _heartbeat_loop(self):
        """Dedicated thread for sending heartbeats to keep the connection alive Regardless of processing load."""
        while self.running:
            now = time.time()
            if self.sock_live and (now - getattr(self, '_sent_live_hb', 0) > (self.heartbeat_interval // 2)):
                self._send_json({"Type": 3}, True)
                self._sent_live_hb = now
            if self.sock_hist and (now - getattr(self, '_sent_hist_hb', 0) > (self.heartbeat_interval // 2)):
                self._send_json({"Type": 3}, False)
                self._sent_hist_hb = now
            time.sleep(1)

    def _connection_manager(self):
        backoff = 1.0
        while self.running:
            # 1. Recovery Check
            # v3.8: Only check sock_hist if we are NOT in Hybrid Mode
            missing_hist = (not self.skip_history and not self.sock_hist)
            if not self.sock_live or missing_hist:
                # MANDATORY Cool-down pause to let Windows clear the socket stack (Error 10065)
                if not getattr(self, '_last_recycle', 0) or (time.time() - self._last_recycle > backoff):
                    print(f"[DTC] Connection gap detected. Re-establishing missing links (Backoff: {backoff}s)...")
                    if self._connect_all():
                        backoff = 1.0 # Reset on success
                    else:
                        backoff = min(backoff * 2, 60.0) # Exponential backoff up to 60s
                    self._last_recycle = time.time()

            # 2. Timeout Monitoring
            now = time.time()
            if self.sock_live and (now - self.last_live_hb > self.heartbeat_interval * 1.5): 
                self._disconnect_all("LIVE timeout", is_live=True, is_hist=False)
            if not self.skip_history and self.sock_hist and (now - self.last_hist_hb > self.heartbeat_interval * 1.5): 
                self._disconnect_all("HIST timeout", is_live=False, is_hist=True)
            
            time.sleep(1)

    def _connect_all(self):
        """Selective connection: Only connect what is missing."""
        try:
            target_host = "127.0.0.1" # Force localhost
            if not self.sock_live:
                self.connect(host=target_host, port=self.port_live, is_live=True)
            
            if not self.skip_history and not self.sock_hist:
                self.connect(host=target_host, port=self.port_hist, is_live=False)

            return True
        except Exception as e:
            print(f"[DTC] Connection failed to {target_host}: {e}")
            return False

    def _disconnect_all(self, reason="Generic", is_live=True, is_hist=True):
        if self.state == DTCState.DISCONNECTED and not self.sock_live and not self.sock_hist:
            return
            
        print(f"[DTC] Disconnecting sockets (LIVE={is_live}, HIST={is_hist}). Reason: {reason}")
        
        # Only change state if we are disconnecting HIST or ALL and not in a state that expects restart
        if is_hist and self.state != DTCState.HIST_WAIT:
            self.state = DTCState.DISCONNECTED
            
        if is_live: self.live_logon = False
        if is_hist: self.hist_logon = False
        
        with self.sock_lock:
            targets = []
            if is_live: targets.append(("LIVE", self.sock_live))
            if is_hist: targets.append(("HIST", self.sock_hist))
            
            for name, s in targets:
                if s: 
                    try: 
                        s.shutdown(socket.SHUT_RDWR)
                        s.close()
                    except Exception as e:
                        print(f"[DTC] Error closing {name} socket: {e}")
            
            if is_live: self.sock_live = None
            if is_hist: self.sock_hist = None

    def _send_json(self, data, is_live):
        self._send_raw((json.dumps(data) + "\0").encode('ascii'), is_live)

    def _send_raw(self, data, is_live):
        with self.sock_lock:
            sock = self.sock_live if is_live else self.sock_hist
            if sock and sock.fileno() != -1:
                try: 
                    sock.sendall(data)
                except OSError as e:
                    # Windows specific error codes
                    werr = getattr(e, 'winerror', 0)
                    if not werr and hasattr(e, 'errno'): werr = e.errno
                    
                    if werr == 10038: 
                        pass # Expected during recycle/shutdown
                    elif werr in [10053, 10054]:
                        pass # Server reset or aborted
                    elif not self.running:
                        pass
                    else:
                        print(f"[DTC] Send Error ({'LIVE' if is_live else 'HIST'}): {e} (Code: {werr})")

    def _receiver_loop(self, sock, is_live):
        buf = b""
        name = "LIVE" if is_live else "HIST"
        try:
            while self.running and sock:
                try:
                    sock.settimeout(1.0)
                    chunk = sock.recv(65536)
                    if not chunk: 
                        print(f"[DTC] {name} Connection closed by remote side.")
                        break
                    buf += chunk
                    while b'\0' in buf:
                        idx = buf.find(b'\0')
                        msg_bytes = buf[:idx]
                        buf = buf[idx+1:]
                        if msg_bytes:
                            try:
                                msg = json.loads(msg_bytes.decode('ascii', 'ignore'))
                                self.msg_queue.put((msg, is_live))
                            except Exception as e:
                                print(f"[DTC] {name} JSON Error: {e}")
                except asyncio.CancelledError:
                    break
                except socket.timeout: 
                    continue
                except OSError as e:
                    werr = getattr(e, 'winerror', 0)
                    if not werr and hasattr(e, 'errno'): werr = e.errno

                    if werr == 10038: 
                        print(f"[DTC] {name} Socket closed locally.")
                        break
                    elif werr in [10053, 10054]:
                        print(f"[DTC] {name} Connection reset/aborted by remote host.")
                        break
                    else:
                        if self.running:
                            print(f"[DTC] {name} Socket Error: {e} (Code: {werr})")
                        break
                except Exception as e:
                    if self.running:
                        print(f"[DTC] {name} Critical Receiver Error: {e}")
                    break
        finally:
            self._disconnect_all(f"{name} receiver loop exit", is_live=is_live, is_hist=not is_live)

    def _processor_loop(self):
        while self.running:
            try:
                # v3.3: Batch Processing with GIL release
                # Grab up to 50 messages or wait 1.0s
                batch = []
                try:
                    # Blocking get for first item
                    item = self.msg_queue.get(timeout=1.0)
                    batch.append(item)
                    # Non-blocking get for rest
                    for _ in range(49):
                        batch.append(self.msg_queue.get_nowait())
                except queue.Empty:
                    pass
                
                if not batch: continue

                # Process batch with sleep to allow heartbeats
                for msg, is_live in batch:
                    mtype = msg.get("Type")
                    if is_live: self.last_live_hb = time.time()
                    else: self.last_hist_hb = time.time()

                    if mtype != 3: 
                        # Reduce log noise for ticks
                        if mtype not in [107, 108]: print(f"[DTC] [DEBUG] {'LIVE' if is_live else 'HIST'} Recv: {mtype}")
                    
                    # Direct processing - Executor overhead is higher than parsing cost for small items
                    # We rely on the periodic sleep below to unblock the heartbeat
                    self._handle_msg(msg, is_live)
                    self.msg_queue.task_done()
                
                # CRITICAL: Yield to Heartbeat Thread
                time.sleep(0.005) 

            except Exception as e:
                print(f"[DTC] Processor Error: {e}")

    def _handle_msg(self, msg, is_live):
        mtype = msg.get("Type")
        if mtype == 2: # Logon Response
            print(f"[DTC] {'LIVE' if is_live else 'HIST'} LOGON RESPONSE: {msg}")
            # Success is usually ResultCode 1, but we'll accept anything that isn't an explicit error
            # Or if "ResultText" is "Success"
            result = msg.get("ResultCode", 1)
            if result != 1 and msg.get("ResultText") != "Success":
                 print(f"[DTC] Logon REJECTED: {msg.get('ResultText')}")
                 return
            
            if is_live:
                self.live_logon = True
                print(f"[DTC] LIVE Logon Success. Subscribing to {len(self.symbols)} assets (MD + Depth)...")
                for sym in self.symbols:
                    sid = self.rev_symbol_id_map.get(sym, 1)
                    # 1. Market Data
                    req = dtc.MarketDataRequest(sid, sym)
                    self._send_raw(req.pack_json(), True)
                    # 2. Market Depth
                    dreq = dtc.MarketDepthRequest(sid, sym, num_levels=20)
                    self._send_raw(dreq.pack_json(), True)
            else:
                self.hist_logon = True
                self.one_hist_req = msg.get("OneHistoricalPriceDataRequestPerConnection", 0) == 1
                if self.one_hist_req:
                    print("[DTC] Server enforces one historical request per connection.")
                
                if self.one_hist_req:
                    print("[DTC] Server enforces one historical request per connection.")
                
                print("[DTC] HIST Logon Success. Requesting History...")
                self.state = DTCState.HIST_WAIT
                self._request_next_history()
        
        elif mtype == 801: # HISTORICAL_PRICE_DATA_RESPONSE_HEADER
            rid = msg.get("RequestID")
            if msg.get("NoRecordsToReturn"):
                print(f"[DTC] No records for {rid}")
                if rid in self.pending_hist_requests:
                    self.pending_hist_requests.remove(rid)
                
                # v3.2: Safely move to next record
                if self.hist_queue and self.hist_queue[0][0] == rid:
                    self.hist_queue.popleft()
                
                if self.hist_queue:
                    print(f"[DTC] Moving to next record in queue...")
                    self._request_next_history()
                elif not self.pending_hist_requests:
                    self.state = DTCState.LIVE
                    print("[DTC] ALL HISTORY SYNCED (No records) -> LIVE")
            else:
                num = msg.get("NumRecords", "Unknown")
                print(f"[DTC] Header for {rid} - Expecting {num} records.")

        elif mtype in [802, 803, 804]: # Records (Float, Tick, or Integer)
            rid = msg.get("RequestID")
            # Collect into temp buffer
            try:
                # Handle both 'LastPrice' (802/804) and 'Price' (803)
                p = msg.get("LastPrice") or msg.get("Price")
                if p:
                    bar = {
                        "time": msg.get("StartDateTime") or msg.get("DateTime"),
                        "open": msg.get("OpenPrice", p),
                        "high": msg.get("HighPrice", p),
                        "low": msg.get("LowPrice", p),
                        "close": p,
                        "volume": msg.get("Volume") or msg.get("Size", 0),
                        "volume": msg.get("Volume") or msg.get("Size", 0),
                        "delta": msg.get("AskVolume", 0) - msg.get("BidVolume", 0)
                    }
                    
                    # v3.4: Delta Simulation for FXCM (if Broker Delta is 0 but Volume > 0)
                    if bar["delta"] == 0 and bar["volume"] > 0:
                         rnge = bar["high"] - bar["low"]
                         if rnge > 0:
                             rel_close = bar["close"] - bar["low"]
                             ratio = rel_close / rnge
                             # Map 0..1 to -1..1
                             approx_factor = (2 * ratio) - 1
                             bar["delta"] = bar["volume"] * approx_factor
                         else:
                             # Doji/Flat bar
                             bar["delta"] = 0
                    
                    self.temp_historical_data.append(bar)
            except: pass
            
            # IsFinalRecord check (Handle both bool and int)
            if msg.get("IsFinalRecord"):
                self.is_downloading = False # Fix A: Allow recycling
                tf = self.request_map.get(rid)
                print(f"[DTC] Final Record received for {rid} ({tf}). Committing {len(self.temp_historical_data)} bars...")
                
                # Commit temp data to global buffer
                if tf:
                    try:
                        from data_feed.dispatcher import ohlc_buffers, delta_buffers
                        if tf in ohlc_buffers:
                            # v3.4: Batched Commit to prevent GIL lockup
                            chunk_size = 5000
                            total = len(self.temp_historical_data)
                            
                            for i in range(0, total, chunk_size):
                                chunk = self.temp_historical_data[i:i+chunk_size]
                                ohlc_buffers[tf].extend(chunk)
                                
                                # Populate delta_buffers from history
                                if tf in delta_buffers:
                                    deltas = [x.get("delta", 0) for x in chunk]
                                    delta_buffers[tf].extend(deltas)
                                
                                # Yield GIL
                                time.sleep(0.005)
                                
                            print(f"[DTC] {tf} Buffer Populated: {len(ohlc_buffers[tf])} bars total. (Batched Commit)")
                    except Exception as e:
                        print(f"[DTC] Error committing {tf} data: {e}")
                
                # v3.2: Only pop if this was the current timeframe
                if self.hist_queue and self.hist_queue[0][0] == rid:
                     self.hist_queue.popleft()
                
                # v3.6: Strict Lifecycle - Always close connection if queue is not empty, 
                # forcing a fresh handshake for the next request.
                if self.hist_queue:
                    print(f"[DTC] Request {rid} finished. Cycling connection for next timeframe...")
                    # Delay closure slightly to ensure OS flushes buffers
                    threading.Timer(0.5, self._disconnect_all, kwargs={"reason": "Strict Recycle", "is_live": False, "is_hist": True}).start()
                    
                    # Schedule reconnection (Manager will pick this up because hist_queue is not empty)
                    # We rely on _connection_manager to see sock_hist is None and reconnect.
                elif not self.pending_hist_requests:
                    self.state = DTCState.LIVE
                    print("[DTC] ALL HISTORY SYNCED -> LIVE")
                    # Optionally close HIST socket to save resources
                    self._disconnect_all(reason="Sync Complete", is_live=False, is_hist=True)

        elif mtype == 107: # Trade
            # v3.9: Multi-Symbol Routing
            sid = msg.get("SymbolID")
            sym = self.symbol_id_map.get(sid)
            if sym and sym in self.engines:
                p, v, agg = msg.get("LastPrice"), msg.get("LastSize"), msg.get("AtBidOrAsk", 0)
                if p and v:
                    dir = 1 if agg == 2 else -1 if agg == 1 else 0
                    self.engines[sym].process_tick(p, v, dir, int(msg.get("DateTime", time.time())))
        
        elif mtype == 101 or mtype == 122: # Depth Update or Snapshot
            sid = msg.get("SymbolID")
            sym = self.symbol_id_map.get(sid)
            if sym and sym in self.depth_engines:
                p = msg.get("Price")
                v = msg.get("Quantity", 0)
                side = msg.get("Side") # 1=Bid, 2=Ask
                if p:
                     self.depth_engines[sym].update(p, v, side)
        
        elif mtype == 3: # Heartbeat
            pass

    def _request_next_history(self):
        if not self.hist_queue: return
        self.is_downloading = True # Fix A: Block recycling until final record
        rid, interval = self.hist_queue[0] # v3.2: Peek instead of pop, robust to reconnects
        print(f"[DTC] Requesting History for {rid} ({interval}s). Waiting for data...")
        req = dtc.HistoricalPriceDataRequest(rid, self.symbols[0], record_interval=interval)
        self._send_raw(req.pack_json(), False)

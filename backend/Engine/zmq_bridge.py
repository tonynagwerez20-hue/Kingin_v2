"""
zmq_bridge.py  —  ZeroMQ Signal Bridge for HedgeEA
=====================================================
Self-healing: automatically installs pyzmq if it is not present.
No manual pip install required.

Architecture:
  Python PUB  →  tcp://*:5555        (HedgeEA subscribes as SUB)
  Python REQ  →  tcp://localhost:5557 (HedgeEA REP — PING/PONG + JSON queries)

Wire protocol:
  PUB message : b"SIGNAL <json_payload>"
  REQ PING    : b"PING"   →  expect b"PONG"
  REQ query   : b'{"type":"GET_BALANCE"}' → expect JSON response
"""

import json
import logging
import subprocess
import sys
import threading
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("ZMQBridge")

class SignalMessage(BaseModel):
    action: str
    symbol: str
    price: float
    sl: float
    tp: float = 0.0
    lots: float
    execution_type: str = "MARKET"
    confluence_score: float = 0.0
    bias: str = "NEUTRAL"
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))



# ── Auto-install pyzmq if missing ────────────────────────────────────────────
def _ensure_pyzmq() -> bool:
    """
    Try to import zmq. If it fails, install pyzmq via pip using the same
    Python interpreter that is running right now, then retry.
    Returns True if zmq is available after this call, False if install failed.
    """
    try:
        import zmq  # noqa: F401
        return True
    except ImportError:
        pass

    logger.warning(
        "[ZMQBridge] pyzmq not found — attempting automatic installation...\n"
        "  Running: %s -m pip install pyzmq", sys.executable
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyzmq", "--quiet"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            logger.info("[ZMQBridge] ✓ pyzmq installed successfully.")
            try:
                import zmq  # noqa: F401
                return True
            except ImportError:
                logger.error(
                    "[ZMQBridge] pyzmq installed but still cannot import. "
                    "Restart the engine to pick up the new package."
                )
                return False
        else:
            logger.error(
                "[ZMQBridge] pip install pyzmq FAILED (code=%d).\n"
                "  stdout: %s\n  stderr: %s\n"
                "  Manual fix: open cmd and run:  pip install pyzmq",
                result.returncode,
                result.stdout.strip(),
                result.stderr.strip(),
            )
            return False
    except Exception as e:
        logger.error(
            "[ZMQBridge] Could not run pip automatically: %s\n"
            "  Manual fix: open cmd and run:  pip install pyzmq", e
        )
        return False


# Run at import time — by the time ZMQBridge.__init__ executes, zmq is ready
_PYZMQ_OK = _ensure_pyzmq()
# ─────────────────────────────────────────────────────────────────────────────


class ZMQBridge:
    """
    Thread-safe ZeroMQ PUB/REQ bridge: Python engine → HedgeEA.mq5.

    PUB socket — binds  tcp://*:<pub_port>       — sends signals to EA SUB
    REQ socket — connects tcp://host:<hb_port>   — pings EA REP heartbeat

    REQ sockets are created fresh per call to avoid state-machine deadlocks.
    """

    _WARMUP_SECS = 0.5

    def __init__(
        self,
        host:          str = "localhost",
        pub_port:      int = 5555,
        hb_port:       int = 5557,
        topic:         str = "SIGNAL",
        hb_timeout_ms: int = 2000,
    ):
        self.host          = host
        self.pub_port      = pub_port
        self.hb_port       = hb_port
        self.topic         = topic
        self.hb_timeout_ms = hb_timeout_ms

        self._lock   = threading.Lock()
        self._ctx    = None
        self._pub    = None
        self._pub_ok = False

        if not _PYZMQ_OK:
            logger.error(
                "[ZMQBridge] Cannot initialize — pyzmq unavailable.\n"
                "  Open cmd and run:  pip install pyzmq  then restart."
            )
            return

        self._setup_pub()

    def _setup_pub(self):
        try:
            import zmq
            self._ctx = zmq.Context()
            self._pub = self._ctx.socket(zmq.PUB)
            self._pub.setsockopt(zmq.SNDHWM, 1000)
            self._pub.setsockopt(zmq.LINGER, 0)

            endpoint = f"tcp://*:{self.pub_port}"
            self._pub.bind(endpoint)
            time.sleep(self._WARMUP_SECS)   # let subscribers connect

            self._pub_ok = True
            logger.info(
                f"[ZMQBridge] ✓ PUB socket bound → {endpoint}  "
                f"topic='{self.topic}'"
            )
        except Exception as e:
            self._pub_ok = False
            logger.error(f"[ZMQBridge] PUB setup failed: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._pub_ok

    def send_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Publish enriched signal dict to HedgeEA via ZMQ PUB socket.
        Logs every field for full dry-run pipeline visibility.
        Returns True on success, False on any error.
        """
        if not self._pub_ok:
            logger.error("[ZMQBridge] send_signal — not ready. Check pyzmq.")
            return False

        try:
            # Validate signal with Pydantic
            validated_signal = SignalMessage(**signal)
            signal_dict = validated_signal.model_dump()
            
            payload = json.dumps(signal_dict, default=str)
            message = f"{self.topic} {payload}"

            with self._lock:
                self._pub.send_string(message)

            logger.info("══════════════ SIGNAL → HEDGEEA ══════════════")
            logger.info(f"  action           = {signal_dict.get('action')}")
            logger.info(f"  symbol           = {signal_dict.get('symbol')}")
            logger.info(f"  price            = {signal_dict.get('price')}")
            logger.info(f"  sl               = {signal_dict.get('sl')}")
            logger.info(f"  tp               = {signal_dict.get('tp')}")
            logger.info(f"  lots             = {signal_dict.get('lots')}")
            logger.info(f"  execution_type   = {signal_dict.get('execution_type')}")
            logger.info(f"  confluence_score = {signal_dict.get('confluence_score')}")
            logger.info(f"  bias             = {signal_dict.get('bias')}")
            logger.info(f"  timestamp        = {signal_dict.get('timestamp')}")
            logger.info("══════════════════════════════════════════════")
            return True

        except Exception as e:
            logger.error(f"[ZMQBridge] send_signal error: {e}")
            return False

    def check_connection(self) -> bool:

        """
        Ping HedgeEA REP socket. Returns True if PONG received.
        Uses a fresh REQ socket each call (avoids state-machine deadlocks).
        """
        if not _PYZMQ_OK:
            return False

        import zmq
        ctx = req = None
        try:
            ctx = zmq.Context()
            req = ctx.socket(zmq.REQ)
            req.setsockopt(zmq.RCVTIMEO, self.hb_timeout_ms)
            req.setsockopt(zmq.SNDTIMEO, self.hb_timeout_ms)
            req.setsockopt(zmq.LINGER,   0)
            req.connect(f"tcp://{self.host}:{self.hb_port}")
            req.send(b"PING")
            reply = req.recv()
            if reply == b"PONG":
                logger.info("[ZMQBridge] ✓ HedgeEA heartbeat OK")
                return True
            logger.warning(f"[ZMQBridge] Unexpected heartbeat reply: {reply}")
            return False
        except zmq.Again:
            logger.warning(
                f"[ZMQBridge] No heartbeat in {self.hb_timeout_ms}ms — "
                "EA may not be running. Signals will queue and deliver when EA starts."
            )
            return False
        except Exception as e:
            logger.warning(f"[ZMQBridge] check_connection error: {e}")
            return False
        finally:
            if req:
                try: req.close()
                except: pass
            if ctx:
                try: ctx.term()
                except: pass

    def query_ea(self, request_type: str, extra: Optional[Dict] = None) -> Optional[Dict]:
        """Send typed JSON query to HedgeEA REP. Returns parsed response or None."""
        if not _PYZMQ_OK:
            return None
        import zmq
        payload = {"type": request_type}
        if extra:
            payload.update(extra)
        ctx = req = None
        try:
            ctx = zmq.Context()
            req = ctx.socket(zmq.REQ)
            req.setsockopt(zmq.RCVTIMEO, self.hb_timeout_ms)
            req.setsockopt(zmq.SNDTIMEO, self.hb_timeout_ms)
            req.setsockopt(zmq.LINGER,   0)
            req.connect(f"tcp://{self.host}:{self.hb_port}")
            req.send_string(json.dumps(payload))
            return json.loads(req.recv_string())
        except Exception as e:
            logger.warning(f"[ZMQBridge] query_ea({request_type}) failed: {e}")
            return None
        finally:
            if req:
                try: req.close()
                except: pass
            if ctx:
                try: ctx.term()
                except: pass

    def close(self):
        """Clean shutdown of PUB socket and ZMQ context."""
        with self._lock:
            if self._pub:
                try: self._pub.close(linger=0)
                except: pass
                self._pub = None
            if self._ctx:
                try: self._ctx.term()
                except: pass
                self._ctx = None
        self._pub_ok = False
        logger.info("[ZMQBridge] Closed.")

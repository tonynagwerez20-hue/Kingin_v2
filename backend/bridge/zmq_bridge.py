"""ZMQ Bridge."""
import asyncio
import json
from typing import Optional

try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False


class ZMQBridge:
    def __init__(self, pub_port: int = 11100, req_port: int = 11101):
        if not ZMQ_AVAILABLE:
            raise RuntimeError("zmq not installed")
        self._ctx = zmq.asyncio.Context()
        self._pub = self._ctx.socket(zmq.PUB)
        self._req = self._ctx.socket(zmq.REQ)
        self._pub_port = pub_port
        self._req_port = req_port
        self._running = False
    
    async def start(self):
        self._pub.bind(f"tcp://127.0.0.1:{self._pub_port}")
        self._req.connect(f"tcp://127.0.0.1:{self._req_port}")
        self._running = True
        print(f"[ZMQ] Bridge started")
    
    async def stop(self):
        self._running = False
        self._pub.close()
        self._req.close()
        self._ctx.term()
    
    async def publish(self, topic: str, data: dict):
        if not self._running:
            return
        msg = json.dumps({"topic": topic, "data": data})
        self._pub.send_string(f"{topic} {msg}")


_bridge: Optional[ZMQBridge] = None

def start_bridge() -> ZMQBridge:
    global _bridge
    if _bridge is None:
        _bridge = ZMQBridge()
    return _bridge
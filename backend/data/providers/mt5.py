"""MT5 Provider."""
from datetime import datetime
from typing import Optional, Dict, Any

class MT5Provider:
    def __init__(self, login: int = 0, password: str = "", server: str = ""):
        self._login = login
        self._password = password
        self._server = server
        self._connected = False
    
    async def connect(self) -> bool:
        self._connected = True
        return True
    
    async def disconnect(self):
        self._connected = False
    
    async def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            return None
        price = 2680.0 + (datetime.now().timestamp() % 100) * 0.01
        return {"time": datetime.now().isoformat(), "symbol": symbol, "bid": price, "ask": price + 0.5}
    
    @property
    def connected(self) -> bool:
        return self._connected


_provider: Optional[MT5Provider] = None

def create_provider(login: int = 0, password: str = "", server: str = "") -> MT5Provider:
    global _provider
    _provider = MT5Provider(login, password, server)
    return _provider
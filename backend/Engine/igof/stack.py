from typing import List, Dict, Optional
import datetime
from .macro import MacroAuctionEngine
from .correlation import CorrelationEngine
from .liquidity import LiquidityEngine
from .v1_engine import V1FiltrationEngine

class FiltrationController:
    def __init__(self, v1_engine: Optional[V1FiltrationEngine] = None):
        self.macro = MacroAuctionEngine()
        self.correlation = CorrelationEngine()
        self.liquidity = LiquidityEngine()
        self.v1 = v1_engine or V1FiltrationEngine()
        # Profile engine is internal to Macro for now? Or separate? 
        # Macro has Weekly Composite. We also need TPO?
        # For simplicity, Macro Engine handles Profile Checks (Location).
        
    def update_batch(self, m5_candles):
        """
        Ingest new M5 candles to update Macro/Profile/TPO state.
        """
        for c in m5_candles:
            # Timestamp to Date String (YYYY-MM-DD)
            # Assuming c['time'] is epoch
            import datetime
            dt = datetime.datetime.fromtimestamp(c['time'])
            date_str = dt.strftime("%Y-%m-%d")
            
            # Update Macro Engine (using Close price for volume - approximation)
            self.macro.update(date_str, c['close'], c['volume'])
            
    def process(self, market_snapshot):
        """
        Main Filter Sequence.
        Input: market_snapshot (dict with price, vol, etc)
        Output: Signal (LONG/SHORT/NO_TRADE)
        """
        # --- NEW V1 MULTI-LAYER FILTRATION ---
        v1_snapshot = {
            "h1_candles": market_snapshot.get("h1_candles", []),
            "m5_candles": market_snapshot.get("m5_candles", []),
            "active_zone": market_snapshot.get("active_zone") # Strategy manager should pass this
        }
        v1_result = self.v1.process_all_layers(v1_snapshot)
        
        if v1_result["action"] == "NO_TRADE":
            return v1_result

        # Legacy logic follows (optional confluence)
        price = market_snapshot.get("price")
        
        # 1. Macro Bias
        context = self.macro.check_context() # BULLISH/BEARISH/NEUTRAL
        
        # 2. Location
        # Check against Weekly Levels
        levels = self.macro.get_levels()
        is_above_poc = price > levels["weekly_poc"]
        # Basic Logic: Bullish Bias + Above POC?
        
        # 3. Correlation (M15)
        # Assume we have data buffers passed in or stored
        # self.correlation.analyze(...)
        corr_res = self.correlation.analyze(
            market_snapshot.get("gc_m15"),
            market_snapshot.get("zn_m15"),
            market_snapshot.get("6e_m15"),
            market_snapshot.get("es_m15")
        )
        
        # 4. Liquidity
        liq_state = self.liquidity.get_market_state(price)
        
        # 5. Delta (Placeholder - can be passed from outside or integrated)
        
        # DECISION MATRIX
        # Rule: No layer limits skipped.
        
        if corr_res["mode"] == "STRICT" and corr_res["signal"] == "NEUTRAL":
            return {"action": "NO_TRADE", "reason": "Correlation Strict & Neutral"}
            
        if context == "BULLISH":
            if corr_res["signal"] == "BEARISH_CONFIRMED":
                return {"action": "NO_TRADE", "reason": "Macro Bullish but Correlation Bearish"}
            # Continue checks...
            return {"action": "LONG_ALLOWED", "reason": "All Clear"}
            
        return {"action": "NO_TRADE", "reason": "Default"}

    def record_trade_outcome(self, signal: Dict, confidence: float, outcome: int, metadata: Optional[Dict] = None):
        """
        Record a trade outcome for the ML layer.
        """
        if hasattr(self.v1, 'record_trade_outcome'):
            return self.v1.record_trade_outcome(signal, confidence, outcome, metadata)
        return False


import time

class LiquidityEngine:
    def __init__(self):
        self.resting_orders = {} # (price, side) -> {start_time, size}
        self.threshold = 10.0 # Lots (Dynamic later)
        self.absorption_events = []
        
    def on_depth_update(self, price, size, side, timestamp=None):
        if timestamp is None: timestamp = time.time()
        key = (price, side)
        
        # Heatmap / Spoof Logic
        if size >= self.threshold:
            if key not in self.resting_orders:
                self.resting_orders[key] = {"start_time": timestamp, "size": size}
            else:
                self.resting_orders[key]["size"] = size
        else:
            if key in self.resting_orders:
                # Liquidity Pulled or Filled
                del self.resting_orders[key]

    def check_heatmap(self, price, side, timestamp=None):
        """Returns True if Real Liquidity exists at price"""
        if timestamp is None: timestamp = time.time()
        key = (price, side)
        if key in self.resting_orders:
            duration = timestamp - self.resting_orders[key]["start_time"]
            return duration > 0.5 # 500ms Spoof Filter
        return False
        
    def detect_absorption(self, trade_price, trade_size, trade_side, dom_snapshot):
        """
        Check for Reloads/Refresh.
        trade_side: 1=Buy(Aggressor), -1=Sell(Aggressor)
        If Buying into Offer (Side 2), and Offer size stays high -> Absorption.
        """
        # Simplified: We need state of DOM *before* trade vs *after*.
        # For now, we assume this is called after trade update, and we check if the level is still thick?
        # A better way is to track "Iceberg" logic: Volume Traded at Price > Visible Size.
        # Placeholder for complex Iceberg logic.
        
        # Simple Logic: If Price is a Heatmap Level AND StartTime is recent (Refresh)?
        pass

    def get_market_state(self, current_price):
        """
        Return liquidity context for current price.
        """
        timestamp = time.time()
        # Check nearby levels (e.g. +/- 5 ticks)
        # return "Liquidity Above" or "Liquidity Below"
        return {
            "heatmap_bid": any(self.check_heatmap(p, side, timestamp) for (p, side) in self.resting_orders if abs(p - current_price) < 2.0 and p < current_price),
            "heatmap_ask": any(self.check_heatmap(p, side, timestamp) for (p, side) in self.resting_orders if abs(p - current_price) < 2.0 and p > current_price)
        }


from .profile import VolumeProfile
from collections import deque

class MacroAuctionEngine:
    def __init__(self):
        self.daily_profiles = {} # DateStr -> VolumeProfile
        self.weekly_composite = VolumeProfile()
        self.naked_pocs = set()
        self.daily_pocs = deque(maxlen=5) # For slope detection
        
    def update(self, date_str, price, volume):
        if date_str not in self.daily_profiles:
            self.daily_profiles[date_str] = VolumeProfile()
            
        # Update Daily
        self.daily_profiles[date_str].update(price, volume)
        
        # Update Composite
        self.weekly_composite.update(price, volume)
        
    def end_of_session(self, date_str):
        """Called at end of RTH to finalize Daily stats"""
        if date_str not in self.daily_profiles: return
        
        prof = self.daily_profiles[date_str]
        prof.calculate_value_area()
        
        # Slope Logic
        self.daily_pocs.append(prof.poc)
        
        # Naked POC Logic
        # Check if yesterday's POC was touched today?
        # Actually, Naked POC is added if it was NOT touched only.
        # Logic: If Daily POC is formed, add to potential Naked list.
        # Then monitor provided ticks to remove it if touched.
        self.naked_pocs.add(prof.poc)

    def check_context(self):
        """
        Determines Bullish/Bearish Context based on Value Migration
        """
        if len(self.daily_pocs) < 2:
            return "NEUTRAL"
        
        # Simple Slope
        curr = self.daily_pocs[-1]
        prev = self.daily_pocs[-2]
        
        if curr > prev: return "BULLISH"
        if curr < prev: return "BEARISH"
        return "BALANCED"

    def get_levels(self):
        """Return Key Levels for Filtration"""
        self.weekly_composite.calculate_value_area()
        return {
            "weekly_poc": self.weekly_composite.poc,
            "weekly_vah": self.weekly_composite.vah,
            "weekly_val": self.weekly_composite.val,
            "naked_pocs": list(self.naked_pocs),
            "context": self.check_context()
        }

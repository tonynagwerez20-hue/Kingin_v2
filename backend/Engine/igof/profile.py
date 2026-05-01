
import numpy as np
from collections import defaultdict

class VolumeProfile:
    def __init__(self, tick_size=0.1):
        self.tick_size = tick_size
        self.volume_at_price = defaultdict(float)
        self.total_volume = 0
        self.poc = 0
        self.vah = 0
        self.val = 0
        self.hvns = []
        self.lvns = []

    def update(self, price, volume):
        # Round to tick size
        p = round(price / self.tick_size) * self.tick_size
        self.volume_at_price[p] += volume
        self.total_volume += volume
        
        # Update POC
        if self.volume_at_price[p] > self.volume_at_price[self.poc]:
            self.poc = p

    def calculate_value_area(self, va_pct=0.70):
        if not self.volume_at_price: return
        
        sorted_prices = sorted(self.volume_at_price.keys())
        # Find index of POC
        try:
            poc_idx = sorted_prices.index(self.poc)
        except ValueError:
            return # Should not happen

        total_captured = self.volume_at_price[self.poc]
        target_vol = self.total_volume * va_pct
        
        low_idx = poc_idx
        high_idx = poc_idx
        
        # Expand out
        while total_captured < target_vol:
            next_low_vol = 0
            next_high_vol = 0
            
            if low_idx > 0:
                next_low_vol = self.volume_at_price[sorted_prices[low_idx-1]]
            
            if high_idx < len(sorted_prices) - 1:
                next_high_vol = self.volume_at_price[sorted_prices[high_idx+1]]
                
            if next_low_vol == 0 and next_high_vol == 0:
                break
                
            if next_low_vol > next_high_vol:
                low_idx -= 1
                total_captured += next_low_vol
            else:
                high_idx += 1
                total_captured += next_high_vol
                
        self.val = sorted_prices[low_idx]
        self.vah = sorted_prices[high_idx]

    def detect_structure(self):
        """Detect HVN/LVN based on simple distribution stats"""
        if not self.volume_at_price: return
        
        vols = list(self.volume_at_price.values())
        if not vols: return
        
        mean_vol = np.mean(vols)
        std_vol = np.std(vols)
        threshold = mean_vol + std_vol
        
        self.hvns = [p for p, v in self.volume_at_price.items() if v > threshold]
        # LVN logic is complex (valleys between peaks), simplified here:
        # Just use low volume nodes inside the value area?
        # Specification says: "Local minima between HVNs"
        # Placeholder for full implementation
        pass

class TPOEngine:
    """Time Price Opportunity (Market Profile)"""
    def __init__(self, tick_size=0.1):
        self.tick_size = tick_size
        self.tpo_at_price = defaultdict(int)
        self.total_tpos = 0
        self.poc = 0
        self.vah = 0
        self.val = 0
    
    def add_bracket(self, open_p, high, low, close):
        """Add a 30m bracket candle"""
        # Iterate every tick in the range? Too slow.
        # Just mark the ticks present in the High-Low range.
        start = int(round(low / self.tick_size))
        end = int(round(high / self.tick_size))
        
        for i in range(start, end + 1):
            p = i * self.tick_size
            self.tpo_at_price[p] += 1
            self.total_tpos += 1
            
            if self.tpo_at_price[p] > self.tpo_at_price.get(self.poc, 0):
                self.poc = p
        
        self.calculate_value_area()
        
    def calculate_value_area(self, va_pct=0.70):
        # Similar logic to Volume Profile but using TPO counts
        if not self.tpo_at_price: return
        sorted_prices = sorted(self.tpo_at_price.keys())
        try:
            poc_idx = sorted_prices.index(self.poc)
        except: return
        
        captured = self.tpo_at_price[self.poc]
        target = self.total_tpos * va_pct
        
        l, h = poc_idx, poc_idx
        
        while captured < target:
            # TPO rules: Check 2 ticks above vs 2 ticks below? 
            # Simplified: 1 tick expansion
            next_l = self.tpo_at_price[sorted_prices[l-1]] if l > 0 else 0
            next_h = self.tpo_at_price[sorted_prices[h+1]] if h < len(sorted_prices)-1 else 0
            
            if next_l == 0 and next_h == 0: break
            
            if next_l > next_h:
                l -= 1
                captured += next_l
            else:
                h += 1
                captured += next_h
                
        self.val = sorted_prices[l]
        self.vah = sorted_prices[h]

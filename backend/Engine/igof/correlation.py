
import pandas as pd
import numpy as np
from collections import deque

class CorrelationEngine:
    """
    IGOF Inter-Market Correlation Filter (M15 Timeframe)
    Assets: GC (Gold), ZN (10Y Note), 6E (Euro), ES (S&P 500)
    """
    def __init__(self):
        self.lookback = 12 # 3 Hours on M15
        self.hard_gate_threshold = -0.7 # Strong Inverse for DXY.. wait, using 6E (Positive)
        # Note: 6E is Positive Correlation with Gold. ZN is Positive Correlation with Gold.
        # DXY is Inverse. 
        # Plan says: "If r < -0.7 ... STRICT MODE". This assumed Inverse.
        # Adjusted for 6E (Positive Proxy): If r > 0.7 (Strong Positive) -> STRICT MODE.
        # If r < 0.3 (Decoupled) -> LOOSE.
        
        self.correlation_threshold = 0.7 
        self.decoupled_threshold = 0.3
        
    def calculate_correlation(self, target_series, proxy_series):
        """Pearson correlation over lookback window"""
        if len(target_series) < self.lookback or len(proxy_series) < self.lookback:
            return 0.0
        
        s1 = pd.Series(list(target_series)[-self.lookback:])
        s2 = pd.Series(list(proxy_series)[-self.lookback:])
        
        return s1.corr(s2)

    def check_structural_divergence(self, gc_candles, proxy_candles, proxy_type="POSITIVE"):
        """
        Checks for Structural Divergence on M15.
        proxy_type: "POSITIVE" (6E, ZN) or "INVERSE" (DXY - not used)
        """
        if len(gc_candles) < 3 or len(proxy_candles) < 3:
            return "WAIT"

        # Current vs Previous 2 (Index -1 vs -2, -3)
        # We need "Session Flow" check. User Spec:
        # "Compare current M15 candle High/Low vs previous 2 M15 candles."
        
        # GC
        gc_curr = gc_candles[-1]
        gc_prev_low = min(c["low"] for c in gc_candles[-3:-1])
        gc_prev_high = max(c["high"] for c in gc_candles[-3:-1])
        
        # Proxy
        p_curr = proxy_candles[-1]
        p_prev_low = min(c["low"] for c in proxy_candles[-3:-1])
        p_prev_high = max(c["high"] for c in proxy_candles[-3:-1])
        
        signal = "NONE"
        
        if proxy_type == "POSITIVE": # 6E, ZN
            # Bullish Divergence: Proxy makes Higher High or Higher Low?
            # User Spec for DXY (Inverse): DXY Higher High -> GC Higher Low (Bullish Div)
            # Transposed to 6E (Positive): 6E Higher High (Dollar dropping) + GC Higher Low?
            # Wait. DXY Higher High = Dollar Strength. GC Higher Low = Relative Strength.
            # 6E Higher High = Dollar Weakness. GC Higher High = Normal.
            # 
            # Let's re-read Spec Step 32:
            # "Bullish Divergence: ZN makes Higher Low (Rates dropping) + GC makes Higher Low."
            # "6E makes Higher High (Dollar dropping) + GC makes Higher Low." 
            # Wait. If Dollar drops (6E Rallies), Gold *should* Rally.
            # Divergence is when they DISAGREE?
            # User Spec 9.2: "Bullish Signal (Relative Strength): DXY makes Higher High (Dollar UP) -> GC makes Higher Low (Gold Resilient)."
            # So: Proxy (Bad for Gold) goes UP, but Gold holds.
            #
            # FOR 6E (Good for Gold):
            # If 6E dumps (Dollar Strength) -> Bad for Gold.
            # If 6E dumps AND Gold makes Higher Low -> BULLISH DIVERGENCE (Relative Strength).
            
            # User Spec Step 32 says:
            # "Bullish Divergence: ZN makes Higher Low... + GC makes Higher Low"
            # This seems like *Confluence* not Divergence.
            # Actually, "We trade divergence, not just correlation."
            # Let's stick to the Specifics in Step 32:
            # "Bullish Divergence: ZN makes Higher Low... + GC makes Higher Low."
            # "6E makes Higher High... + GC makes Higher Low."
            # This describes a TREND ALIGNMENT (Confluence) scan?
            # "Translation: DXY made a new high... Gold refused to make a new low."
            # DXY New High = Bad. Gold Refused Low = Good. -> Bullish Divergence.
            
            # Transposing DXY New High (Bad) to 6E:
            # 6E New Low (Bad).
            # So: 6E New Low + GC Higher Low = Bullish Divergence.
            
            # BUT User Spec 32 says:
            # "Bullish Divergence: 6E makes Higher High (Dollar dropping) + GC makes Higher Low."
            # High High on 6E is Good. GC HL is Good. This is bullish confluence.
            # Maybe the user calls it "Divergence" but means "Signal"?
            # "Bullish Signal (Relative Strength): DXY High High -> GC High Low" (This is classic divergence).
            #
            # The user's Step 32 text is contradictory or I am misinterpreting "ZN makes Higher Low".
            # ZN Price Up = Yields Down = Bullish for Gold.
            # ZN Higher Low = Bullish Trend.
            #
            # Let's implement BOTH: Confluence (Confirmation) and Divergence (Relative Strength).
            # Or stick strictly to the User's "Section 9.2 Revised" text in Step 32.
            # "Bullish Divergence: ZN makes Higher Low... + GC makes Higher Low."
            # "6E makes Higher High... + GC makes Higher Low."
            
            # Implementation:
            # Check ZN Trend: Is Current Low > Previous Lows? (Higher Low)
            # Check GC Trend: Is Current Low > Previous Lows? (Higher Low)
            pass

        return signal

    def analyze(self, gc_data, zn_data, e6_data, es_data):
        """
        Main Analysis Entry Point
        """
        # 1. Pearson Correlation
        if not gc_data or not zn_data: return {"status": "WAIT"}
        
        # Extract closing prices for Pearson
        gc_closes = [c["close"] for c in gc_data]
        zn_closes = [c["close"] for c in zn_data]
        e6_closes = [c["close"] for c in e6_data]
        
        r_zn = self.calculate_correlation(gc_closes, zn_closes)
        r_6e = self.calculate_correlation(gc_closes, e6_closes)
        
        avg_corr = (r_zn + r_6e) / 2
        
        # 2. Structural Check
        # Logic from Step 32:
        # Bullish: ZN Higher Low + GC Higher Low
        # Bearish: ZN "Dumps" (Lower Low?) + GC Fails to Rally (Lower High?)
        
        # Helper for Higher Low / Lower Low
        def is_higher_low(candles):
            if len(candles) < 3: return False
            curr_low = candles[-1]["low"]
            prev_lows = min(c["low"] for c in candles[-3:-1])
            return curr_low > prev_lows

        def is_lower_high(candles):
             if len(candles) < 3: return False
             curr_high = candles[-1]["high"]
             prev_highs = max(c["high"] for c in candles[-3:-1])
             return curr_high < prev_highs

        def is_dumping(candles):
            # Close < Low of previous 2
            if len(candles) < 3: return False
            curr_close = candles[-1]["close"]
            prev_lows = min(c["low"] for c in candles[-3:-1])
            return curr_close < prev_lows

        gc_hl = is_higher_low(gc_data)
        zn_hl = is_higher_low(zn_data)
        e6_hh = is_higher_low(e6_data) # Using HL logic for HH check? No need proper HH
        
        # 6E Higher High logic
        def is_higher_high(candles):
            if len(candles) < 3: return False
            curr_high = candles[-1]["high"]
            prev_highs = max(c["high"] for c in candles[-3:-1])
            return curr_high > prev_highs

        e6_hh = is_higher_high(e6_data)
        
        signal = "NEUTRAL"
        
        # Bullish Logic
        # ZN makes Higher Low + GC Higher Low
        if zn_hl and gc_hl:
            signal = "BULLISH_CONFIRMED"
        # 6E makes Higher High + GC Higher Low
        if e6_hh and gc_hl:
            signal = "BULLISH_CONFIRMED"
            
        # Bearish Logic
        # ZN Dumps + GC Fails to Rally (Lower High or dumping)
        zn_dump = is_dumping(zn_data)
        gc_weak = is_lower_high(gc_data) or is_dumping(gc_data)
        
        if zn_dump and gc_weak:
            signal = "BEARISH_CONFIRMED"
            
        return {
            "avg_correlation": avg_corr,
            "zn_corr": r_zn,
            "e6_corr": r_6e,
            "mode": "STRICT" if abs(avg_corr) > self.correlation_threshold else "LOOSE",
            "signal": signal
        }

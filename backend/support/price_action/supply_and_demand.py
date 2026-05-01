import pandas as pd

def detect_supply_demand(df, lookback = 5, threshold = 1.5):
    """
    Detect supply and demand zones from OHLC data.
    optimized for rolling OHLC dataframes
    """

    zones =[]

    for i in range(lookback, len(df)):
        rng = df['high'].iloc[i] - df['low'].iloc[i]
        prev_rng =df['high'].iloc[i - lookback] - df['low'].iloc[i - lookback]

        # Demand Zone
        if(
            df['low'].iloc[i] < df['low'].iloc[i - 1] and
            df['close'].iloc[i] > df['open'].iloc[i] and 
            rng > prev_rng / threshold
        ):
            zones.append({
                "type": "demand",
                "low": df['low'].iloc[i],
                "high": df['close'].iloc[i],
                "index":i
            })
        
        # Supply Zone (Bearish)
        if(
            df['high'].iloc[i] > df['high'].iloc[i - 1] and
            df['close'].iloc[i] < df['open'].iloc[i] and 
            rng > prev_rng / threshold
        ):
            zones.append({
                "type": "supply",
                "low": df['close'].iloc[i],
                "high": df['high'].iloc[i],
                "index": i
            })         
    return zones

def mitigate_zones(zones, current_price):
    """
    Remove invalidated zones based on current price.
    - Demand broken if price < low
    - Supply broken if price > high
    """
    if not zones:
        return []
        
    valid_zones = []
    for z in zones:
        if z["type"] == "demand":
            if current_price >= z["low"]:
                valid_zones.append(z)
        elif z["type"] == "supply":
            if current_price <= z["high"]:
                valid_zones.append(z)
                
    return valid_zones

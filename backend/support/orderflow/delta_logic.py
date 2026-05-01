from math import fabs

def evaluate_delta(delta_struct,epsilon=2.0):
    """"
    Delta Logic:
    - flip
    - surge
    - transition
    with cumulative delta validation
    """

    d = delta_struct["delta"]
    dmax = delta_struct["max"]
    dmin = delta_struct["min"]
    cdelta =delta_struct["cumulative"]

    # Minimum requirement for any logic (FLIP needs 2)
    if len(d) < 2:
        return None

    # Safe access to recent bars
    d0 = d[0]
    d1 = d[1]
    
    #======DELTA FLIP (Requires 2 bars)=======
    if d1 < 0 and d0 > 0:
        if fabs(dmax[0] - d0) < epsilon and fabs(dmin[0]) <epsilon:
            if cdelta[0] > 0:
                return"BUY_FLIP"
    

    if d1 > 0 and d0 < 0:
        if fabs(dmax[0] - d0) < epsilon and fabs(dmin[0]) < epsilon:
            if cdelta[0] < 0:
                return"SELL_FLIP"
            
    #======DELTA SURGE & TRANSITION (Requires 4 bars)======
    if len(d) >= 4:
        d2, d3 = d[2], d[3]
        
        # SURGE
        if(
            d3 <= 0 and d2 > 0 and abs(d2) > abs(d3) and 
            d1 > 0 and abs(d1) > abs(d2) and
            d0 > 0 and abs(d0) > abs(d1) and
            cdelta[0] > 0 
        ):
            return"BUY_SURGE"
        
        if(
            d3 >= 0 and d2 < 0 and abs(d2) > abs(d3) and 
            d1 < 0 and abs(d1) > abs(d2) and
            d0 < 0 and abs(d0) > abs(d1) and
            cdelta[0] < 0 
        ):
            return"SELL_SURGE"
        
        # TRANSITION
        if d3 < 0 and d2 > d3 and d1 > d2 and d0 > d1:
            if cdelta[0] > 0:
                return"BUY_TRANSITION"
            
        if d3 > 0 and d2 < d3 and d1 < d2 and d0 < d1:
            if cdelta[0] < 0:
                return"SELL_TRANSITION"
        
    return None


def get_delta_direction(delta_signal: str) -> str:
    """
    Extract direction from delta signal.
    
    Args:
        delta_signal: Signal like "BUY_FLIP", "SELL_SURGE", etc.
        
    Returns:
        "BUY", "SELL", or "NONE"
    """
    if not delta_signal:
        return "NONE"
    
    if "BUY" in delta_signal:
        return "BUY"
    elif "SELL" in delta_signal:
        return "SELL"
    
    return "NONE"


def detect_delta_reversal(previous_signal: str, current_signal: str, strong_only: bool = False) -> bool:
    """
    Detect if delta signal has reversed direction.
    
    Args:
        previous_signal: Previous delta signal
        current_signal: Current delta signal
        strong_only: If True, only consider FLIP/SURGE as reversals (not TRANSITION)
        
    Returns:
        True if reversal detected, False otherwise
    """
    if not previous_signal or not current_signal:
        return False
    
    prev_dir = get_delta_direction(previous_signal)
    curr_dir = get_delta_direction(current_signal)
    
    # No reversal if directions are same or either is NONE
    if prev_dir == curr_dir or prev_dir == "NONE" or curr_dir == "NONE":
        return False
    
    # If strong_only, check that current signal is FLIP or SURGE
    if strong_only:
        if "TRANSITION" in current_signal:
            return False
    
    # Directions are opposite - reversal detected
    return True

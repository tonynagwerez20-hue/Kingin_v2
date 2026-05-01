def calculate_lot_size(account_balance: float, stop_loss_pips: float, pip_value_per_lot: float, risk_pct: float = 0.01) -> float:
    """
    Calculate lot size based on risk percentage and stop loss.
    """
    if stop_loss_pips <= 0:
        return 0.01
        
    risk_amount = account_balance * risk_pct
    
    # risk = lots * sl_pips * pip_value
    # lots = risk / (sl_pips * pip_value)
    
    # Avoid division by zero
    if pip_value_per_lot <= 0:
        return 0.01
        
    lots = risk_amount / (stop_loss_pips * pip_value_per_lot)
    
    # Round to 2 decimal places (standard for lots)
    return round(max(0.01, lots), 2)

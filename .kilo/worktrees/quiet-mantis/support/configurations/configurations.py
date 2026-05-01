
"""
Risk Management Configuration and Logic.
"""

RISK_PER_TRADE_PERCENT = 0.001  # 0.1%
MAX_DAILY_DRAWDOWN_PERCENT = 0.025  # 2.5%
MIN_LOT_SIZE = 0.01

def calculate_lot_size(account_balance: float, stop_loss_pips: float, pip_value_per_lot: float = 10.0) -> float:
    """
    Calculate position size based on risk percentage.
    
    Args:
        account_balance: Current account balance.
        stop_loss_pips: Distance to stop loss in pips.
        pip_value_per_lot: Value of 1 pip for a standard lot (default $10 for standard lot).
        
    Returns:
        float: Calculated lot size, floored to 2 decimal places, min 0.01.
    """
    if stop_loss_pips <= 0:
        return MIN_LOT_SIZE
        
    risk_amount = account_balance * RISK_PER_TRADE_PERCENT
    
    # Risk = Lots * StopLoss * PipValue
    # Lots = Risk / (StopLoss * PipValue)
    
    raw_lots = risk_amount / (stop_loss_pips * pip_value_per_lot)
    
    # Round down to 2 decimal places to be safe
    lots = int(raw_lots * 100) / 100.0
    
    return max(MIN_LOT_SIZE, lots)

def check_drawdown_limit(current_daily_loss: float, account_balance_start_of_day: float) -> bool:
    """
    Check if the maximum daily drawdown has been reached.
    
    Args:
        current_daily_loss: Total loss for the day (positive value).
        account_balance_start_of_day: Account balance at the start of the day.
        
    Returns:
        bool: True if trading should stop (limit reached), False otherwise.
    """
    max_loss = account_balance_start_of_day * MAX_DAILY_DRAWDOWN_PERCENT
    return current_daily_loss >= max_loss

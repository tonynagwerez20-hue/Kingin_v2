import logging
from typing import Dict
from Engine.base_interfaces import BaseRiskRule

logger = logging.getLogger("UltraLowAccountRisk")

class UltraLowAccountRiskRule(BaseRiskRule):
    """
    Risk rule specifically designed for accounts between $10 and $15.
    Focuses on extreme capital preservation and margin management.
    Now with AUTO-SIZING: increases lot size with profit, decreases with losses.
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.min_equity = config.get("min_equity_threshold", 7.50)
        self.base_daily_loss_pct = config.get("max_daily_loss_pct", 5.0)
        self.base_max_positions = config.get("max_concurrent_positions", 1)
        self.min_lot_size = config.get("min_lot_size", 0.01)  # Minimum micro-lot
        self.max_lot_size = config.get("max_lot_size", 0.1)   # Maximum lot size
        self.seed_balance = config.get("seed_balance", 10.0) # Starting point for scaling
        self.profit_step = config.get("profit_step_for_scaling", 15.0) # Scale every $15
        self.risk_pct_per_trade = config.get("risk_pct_per_trade", 0.01) # 1% risk per trade

    def calculate_auto_lot_size(self, current_equity: float, seed_balance: float = None) -> float:
        """
        AUTO-SIZING LOGIC:
        - Increases lot size when in profit (above seed balance)
        - Decreases lot size when in loss (below seed balance)
        - Uses linear scaling between min and max lot sizes
        """
        # Allow runtime override so the bootstrapper can pass the actual
        # account opening balance instead of the config default.
        effective_seed = seed_balance if seed_balance is not None else self.seed_balance
        profit = current_equity - effective_seed
        
        if profit >= 0:
            # In profit: scale up proportionally
            # For every $5 profit, increase lot size
            profit_steps = int(profit / self.profit_step)
            # Scale factor: 1 step = 0.01 increase (from 0.01 to 0.02, etc.)
            scaled_lot = self.min_lot_size + (profit_steps * 0.01)
        else:
            # In loss: scale down proportionally
            # For every $2.5 loss below seed, decrease by 0.01
            loss_steps = int(abs(profit) / 2.5)
            scaled_lot = self.min_lot_size - (loss_steps * 0.01)
        
        # Clamp to min/max bounds
        final_lot = max(self.min_lot_size, min(self.max_lot_size, scaled_lot))
        
        logger.info(f"Auto-Sizing: Equity=${current_equity:.2f}, Profit=${profit:.2f}, Lot={final_lot:.3f}")
        return final_lot

    def check_risk(self, trade_request: Dict) -> Dict:
        """
        Evaluates the trade request against dynamic small-account constraints.
        Now with AUTO-SIZING: lot size scales with account performance.
        """
        current_equity = trade_request.get("current_equity", 0.0)
        daily_loss = trade_request.get("daily_loss", 0.0)
        daily_start_balance = trade_request.get("daily_start_balance", current_equity)
        
        # --- DYNAMIC RISK TIGHTENING ---
        # If we are in account-level drawdown (equity < seed), tighten risk
        current_daily_loss_limit = self.base_daily_loss_pct
        if current_equity < self.seed_balance:
            current_daily_loss_limit = self.base_daily_loss_pct / 2.0
            logger.info(f"Risk Tightening Active: Daily limit reduced to {current_daily_loss_limit}%")

        # --- DYNAMIC EXPOSURE SCALING ---
        # Scale positions based on profit: 1 pos for $10, 2 for $15, 3 for $20, etc.
        profit = max(0, current_equity - self.seed_balance)
        scaling_bonus = int(profit / self.profit_step)
        dynamic_max_positions = self.base_max_positions + scaling_bonus
        
        # 1. Equity Protection Check
        if current_equity < self.min_equity:
            logger.warning(f"Trade Denied: Equity (${current_equity:.2f}) is below safety floor (${self.min_equity:.2f})")
            return {
                "allowed": False,
                "reason": f"Equity safety floor reached: ${current_equity:.2f} < ${self.min_equity:.2f}",
                "dynamic_limit": current_daily_loss_limit,
                "dynamic_max_positions": dynamic_max_positions
            }

        # 2. Daily Loss Percentage Check
        loss_pct = (daily_loss / daily_start_balance) * 100 if daily_start_balance > 0 else 0
        if loss_pct >= current_daily_loss_limit:
            logger.warning(f"Trade Denied: Daily loss limit reached ({loss_pct:.2f}% >= {current_daily_loss_limit}%)")
            return {
                "allowed": False,
                "reason": f"Daily % loss limit reached: {loss_pct:.2f}% (Dynamic Limit: {current_daily_loss_limit}%)",
                "dynamic_limit": current_daily_loss_limit,
                "dynamic_max_positions": dynamic_max_positions
            }

        # 3. Dynamic Position Gating
        open_positions = trade_request.get("open_positions_count", 0)
        if open_positions >= dynamic_max_positions:
            logger.warning(f"Trade Denied: Max positions reached ({open_positions} >= {dynamic_max_positions})")
            return {
                "allowed": False,
                "reason": f"Exposure Limit: {dynamic_max_positions} positions allowed @ ${current_equity:.2f} equity.",
                "dynamic_limit": current_daily_loss_limit,
                "dynamic_max_positions": dynamic_max_positions
            }

        # AUTO-SIZING: Calculate dynamic lot size based on account performance.
        # Prefer seed_balance passed in the trade_request (from the bootstrapper's
        # live account data) over the static config value — ensures correct scaling
        # even when the account is refunded or top-up-ed.
        signal_seed = trade_request.get("seed_balance", None)
        dynamic_lot_size = self.calculate_auto_lot_size(current_equity, seed_balance=signal_seed)
        trade_request["lots"] = dynamic_lot_size

        return {
            "allowed": True,
            "reason": f"Safety checks passed. Auto-size: {dynamic_lot_size:.3f} lots, Positions: {dynamic_max_positions} allowed.",
            "enforced_lots": dynamic_lot_size,
            "dynamic_limit": current_daily_loss_limit,
            "dynamic_max_positions": dynamic_max_positions
        }

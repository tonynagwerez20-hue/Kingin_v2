import pandas as pd
import numpy as np
import random
from pathlib import Path
from typing import Dict, List, Any

class MonteCarloEngine:
    """
    Performs Monte Carlo simulations on trade signals to assess risk and performance.
    """
    def __init__(self, signals_file: str = "data/backtest_signals.csv"):
        self.project_root = Path(__file__).parent.parent.parent
        self.signals_path = self.project_root / signals_file
        self.results = {}

    def load_signals(self) -> pd.DataFrame:
        if not self.signals_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.signals_path)

    def run_simulation(self, iterations: int = 1000, slippage_pips: float = 2.0, initial_balance: float = 10000.0):
        """
        Runs a Monte Carlo simulation by shuffling trades and applying slippage.
        """
        df = self.load_signals()
        if df.empty:
            return {"status": "ERROR", "message": "No signals found for simulation."}

        # Convert signals to returns (simplified: 10 pips = 1% gain for 0.1 lot on Gold etc.)
        # In a real system, we'd calculate PnL based on entry/exit or fixed R:R
        # For simulation, we assume each trade has a random result based on a normal distribution
        # derived from the signal 'Desc' or a default profitable edge.
        
        # Mocking returns based on a 60% win rate and 1:2 R:R
        win_rate = 0.60
        risk_reward = 2.0
        risk_per_trade = 0.01 # 1%
        
        simulation_data = []
        
        for i in range(iterations):
            balance = initial_balance
            equity_curve = [balance]
            trades = list(df.index)
            random.shuffle(trades) # The Monte Carlo "Shuffle"
            
            for _ in trades:
                # Apply slippage logic
                is_win = random.random() < win_rate
                if is_win:
                    profit = balance * risk_per_trade * risk_reward
                    balance += profit
                else:
                    loss = balance * risk_per_trade
                    balance -= (loss + (slippage_pips * 10)) # Penalty
                
                equity_curve.append(balance)
            
            simulation_data.append({
                "final_balance": balance,
                "max_drawdown": self._calculate_max_drawdown(equity_curve),
                "equity_curve": equity_curve
            })

        self.results = {
            "iterations": iterations,
            "avg_final_balance": np.mean([s["final_balance"] for s in simulation_data]),
            "max_drawdown_avg": np.mean([s["max_drawdown"] for s in simulation_data]),
            "prob_of_ruin": len([s for s in simulation_data if s["final_balance"] < initial_balance * 0.5]) / iterations,
            "simulations": simulation_data[:10] # Return a sample for graphing
        }
        
        return self.results

    def _calculate_max_drawdown(self, equity_curve):
        peak = equity_curve[0]
        max_dd = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

# Example usage interface for the Dashboard
def get_stress_test_report(iterations=1000):
    engine = MonteCarloEngine()
    return engine.run_simulation(iterations=iterations)

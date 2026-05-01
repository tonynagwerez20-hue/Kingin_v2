import QuantLib as ql
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import sys
from datetime import datetime, timedelta

# Add root project to sys path to import support modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from support.strategies.filter_one import FilterOne
from support.strategies.filter_two import FilterTwo
from support.strategies.candlestick_trigger import CandlestickStrategy
from support.risk.risk_calculator import RiskCalculator
from support.risk.cro_rules import CRORules

class MonteCarloEngine:
    def __init__(self, spot_price=5032.44, vol=0.5119, drift=1.2142, risk_free_rate=0.04):
        self.spot_price = spot_price
        self.vol = vol
        self.drift = drift
        self.risk_free_rate = risk_free_rate
        
        # Strategy components (Replicating simple_signal_generator.py variables)
        self.f1 = FilterOne()
        self.f2 = FilterTwo()
        self.cs = CandlestickStrategy()
        
        # Replicate exactly: balance=100.0, risk=0.001
        self.risk_calc = RiskCalculator(account_balance=100.0, risk_percent=0.001)
        
        # Replicate exactly: max_spread=5.0
        self.cro = CRORules(max_spread_pips=5.0)

    def generate_path(self, days=5, dt_minutes=5):
        """Generates a stochastic path of XAUUSD at 5-minute intervals."""
        # Setup QuantLib GBM process
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()
        
        start_date = ql.Date(15, ql.February, 2026)
        ql.Settings.instance().evaluationDate = start_date
        
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(self.spot_price))
        rate_handle = ql.YieldTermStructureHandle(ql.FlatForward(start_date, self.risk_free_rate, day_count))
        vol_handle = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(start_date, calendar, self.vol, day_count))
        
        dividend_yield = self.risk_free_rate - (self.drift - 0.5 * self.vol**2)
        div_handle = ql.YieldTermStructureHandle(ql.FlatForward(start_date, dividend_yield, day_count))
        
        process = ql.BlackScholesMertonProcess(spot_handle, div_handle, rate_handle, vol_handle)
        
        steps_per_day = (24 * 60) // dt_minutes
        total_steps = int(days * steps_per_day)
        t = days / 365.0
        
        rng = ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(total_steps, ql.UniformRandomGenerator()))
        seq = ql.GaussianPathGenerator(process, t, total_steps, rng, False)
        
        path = seq.next().value()
        prices = [path[i] for i in range(len(path))]
        
        base_time = datetime(2026, 2, 15, 0, 0)
        timestamps = [base_time + timedelta(minutes=i * dt_minutes) for i in range(len(prices))]
        
        return list(zip(timestamps, prices))

    def run_simulation(self, iterations=200):
        print(f"Starting Engine-Synchronized Monte Carlo Simulation ({iterations} iterations)...")
        results = []
        
        # Aggregate statistics similar to simple_signal_generator.py
        total_rejected_stats = {
            "filter_one": 0,
            "filter_two": 0,
            "alignment": 0,
            "candlestick": 0,
            "cro_audit": 0
        }
        
        for i in range(iterations):
            path_data = self.generate_path(days=5) # Simulate 1 trading week
            trades, path_stats = self.evaluate_path(path_data)
            
            pnl = sum(t["pnl"] for t in trades)
            trades_count = len(trades)
            win_rate = (sum(1 for t in trades if t["pnl"] > 0) / trades_count) if trades_count > 0 else 0
            
            # Update global stats
            for key in total_rejected_stats:
                total_rejected_stats[key] += path_stats.get(key, 0)
            
            results.append({
                "iteration": i,
                "trades_count": trades_count,
                "win_rate": win_rate,
                "profit": pnl
            })
            if (i+1) % 50 == 0:
                print(f"  Processed {i+1}/{iterations} iterations...")
                
        self.report_results(results, total_rejected_stats)

    def evaluate_path(self, path_data):
        """Runs the strategy logic against a single stochastic path mirroring perfectly simple_signal_generator.py."""
        m5_bars = []
        for i in range(1, len(path_data)):
            ts, close = path_data[i]
            prev_ts, prev_close = path_data[i-1]
            
            # Replicating M5 bar simulation
            m5_bars.append({
                "timestamp": ts.timestamp(),
                "open": prev_close,
                "high": max(prev_close, close) + abs(close-prev_close)*0.1,
                "low": min(prev_close, close) - abs(close-prev_close)*0.1,
                "close": close,
                "volume": 1200 + np.random.randint(-200, 200), # Simulated volume
                "delta": np.random.randint(-100, 100) # Simulated delta
            })
            
        trades = []
        h1_buf = []
        m15_buf = []
        m5_buf = []
        
        path_rejected_stats = {
            "filter_one": 0,
            "filter_two": 0,
            "alignment": 0,
            "candlestick": 0,
            "cro_audit": 0
        }
        
        active_trade = None
        
        for idx, bar in enumerate(m5_bars):
            m5_buf.append(bar)
            if len(m5_buf) > 300: m5_buf.pop(0)
            
            if len(m5_buf) < 100: continue
            
            # Simple aggregation (Replicating the Buffer logic)
            h1_sim = m5_buf[::12]
            m15_sim = m5_buf[::3]
            
            # 1. Manage Active Trade (Simulation specific outcome)
            if active_trade:
                if active_trade["action"] == "LONG":
                    if bar["high"] >= active_trade["tp"]:
                        trades.append({"action": "LONG", "pnl": active_trade["risk"] * 3}) # 1:3 RR
                        active_trade = None
                    elif bar["low"] <= active_trade["sl"]:
                        trades.append({"action": "LONG", "pnl": -active_trade["risk"]})
                        active_trade = None
                else: # SHORT
                    if bar["low"] <= active_trade["tp"]:
                        trades.append({"action": "SHORT", "pnl": active_trade["risk"] * 3})
                        active_trade = None
                    elif bar["high"] >= active_trade["sl"]:
                        trades.append({"action": "SHORT", "pnl": -active_trade["risk"]})
                        active_trade = None
                if not active_trade: 
                    continue # Re-evaluation only after trade close

            # 2. EVALUATION LOGIC - PARITY WITH simple_signal_generator.py
            
            # A. Trigger First (Candlestick Pattern)
            cs_res = self.cs.evaluate(h1_sim, m15_sim, m5_buf)
            if not cs_res:
                path_rejected_stats["candlestick"] += 1
                continue
                
            trigger_action = cs_res["action"]
            price = bar["close"]
            
            # B. CRO Audit
            market_data = {
                "spread": 2.2, # Simulated average gold spread
                "volume": bar["volume"]
            }
            audit_res = self.cro.audit_trade_request({}, market_data)
            
            if audit_res["status"] == "FAIL":
                path_rejected_stats["cro_audit"] += 1
                continue
                
            # C. Filter One (Bias)
            f1_res = self.f1.evaluate(h1_sim, m15_sim, m5_buf)
            if not f1_res or f1_res["action"] != trigger_action:
                path_rejected_stats["filter_one"] += 1
                continue
                
            # D. Filter Two (Zones)
            kwargs = {"active_zone": f1_res.get("active_zone")}
            f2_res = self.f2.evaluate(h1_sim, m15_sim, m5_buf, **kwargs)
            if not f2_res or f2_res["action"] != trigger_action:
                path_rejected_stats["filter_two"] += 1
                continue
                
            # E. Risk Calculation
            risk_params = self.risk_calc.calculate_trade_params(trigger_action, price, f2_res.get("active_zone"))
            sl = risk_params["sl"]
            
            # TP Calculation (Backtest standard: 3x risk)
            tp_pips = risk_params["sl_pips"] * 3.0
            tp = price + (tp_pips / 10) if trigger_action == "LONG" else price - (tp_pips / 10)
            
            # Risk amount matches generator logic ($0.10 for $100 account micro-lots)
            # Replicating lot sizing effect
            risk_amount = (risk_params["lots"] / 0.01) * 0.01 # Simplified PnL mapping

            active_trade = {
                "action": trigger_action,
                "entry": price,
                "sl": sl,
                "tp": tp,
                "risk": 0.10 # Replicating 0.1% absolute risk for 100$ balance
            }
                        
        return trades, path_rejected_stats

    def report_results(self, results, total_rejected_stats):
        df = pd.DataFrame(results)
        data_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        csv_path = os.path.join(data_dir, "mc_results_parity.csv")
        md_path = os.path.join(data_dir, "mc_report_summary.md")
        plot_path = os.path.join(data_dir, "mc_distribution.png")
        
        df.to_csv(csv_path, index=False)
        
        # 1. GENERATE PLOT
        plt.figure(figsize=(10, 6))
        plt.hist(df['profit'], bins=30, color='skyblue', edgecolor='black', alpha=0.7)
        plt.axvline(df['profit'].mean(), color='red', linestyle='dashed', linewidth=2, label=f"Avg: ${df['profit'].mean():.2f}")
        plt.axvline(df['profit'].quantile(0.05), color='orange', linestyle='dotted', linewidth=2, label=f"VaR (95%): ${df['profit'].quantile(0.05):.2f}")
        plt.title("Monte Carlo P&L Distribution (XAUUSD Strategy)")
        plt.xlabel("Profit/Loss ($)")
        plt.ylabel("Frequency")
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        plt.savefig(plot_path)
        plt.close()

        # 2. GENERATE MARKDOWN REPORT
        var_95 = df['profit'].quantile(0.05)
        prob_ruin = (df['profit'] < -1.0).mean() * 100 
        
        report_content = f"""# Monte Carlo Simulation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Asset: XAUUSD | Balance: $100

## Executive Summary
- **Total Iterations:** {len(df)}
- **Avg Profit / Week:** ${df['profit'].mean():.2f}
- **Avg Win Rate:** {df['win_rate'].mean()*100:.2f}%
- **Avg Trades / Week:** {df['trades_count'].mean():.2f}

## Risk Metrics
- **Value at Risk (95%):** ${var_95:.2f}
- **Probability of Ruin (>1% Weekly DD):** {prob_ruin:.2f}%

## Visual Distribution
![PnL Distribution](mc_distribution.png)

## Veto Analysis
| Filter | Rejections |
| :--- | :--- |
| Filter One (Bias) | {total_rejected_stats.get('filter_one', 0)} |
| Filter Two (Zones) | {total_rejected_stats.get('filter_two', 0)} |
| Candlestick | {total_rejected_stats.get('candlestick', 0)} |
| CRO Audit | {total_rejected_stats.get('cro_audit', 0)} |

---
*Raw Data: [mc_results_parity.csv](mc_results_parity.csv)*
"""
        with open(md_path, "w") as f:
            f.write(report_content)

        print("\n" + "="*50)
        print("MONTE CARLO SYNC REPORT (ENGINE PARITY)")
        print("="*50)
        print(f"Total Iterations: {len(df)}")
        print(f"Avg Profit/Week:  ${df['profit'].mean():.2f}")
        print(f"Avg Win Rate:     {df['win_rate'].mean()*100:.2f}%")
        print(f"Value at Risk (95%): ${var_95:.2f}")
        print(f"Prob. of Ruin (>1% DD): {prob_ruin:.2f}%")
        print("\nREPORTS GENERATED:")
        print(f"  [HTML/MD]  {md_path}")
        print(f"  [PLOT]     {plot_path}")
        print(f"  [RAW CSV]  {csv_path}")
        print("="*50)

if __name__ == "__main__":
    engine = MonteCarloEngine()
    engine.run_simulation(iterations=200)

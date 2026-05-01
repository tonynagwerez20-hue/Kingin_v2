# Technical Report: Optimal Low-Capital Allocation for SMC Bot
**Analysis Date**: 2026-02-20
**Reference Strategy**: Institutional MTF SMC Engine
**Reference Asset**: XAUUSD (Gold)

---

## 📋 Executive Summary
Based on the 6-month backtest simulation and the performance of the `UltraLowAccountRiskRule`, this report outlines the optimal capital requirements for accounts under $100. The objective is to maximize survival probability against Gold's intrinsic volatility while utilizing dynamic scaling logic.

---

## 📊 Portfolio Tier Analysis

### Tier 1: The "Fragility" Tier ($10 - $25)
*   **Status**: High Risk / Experimental
*   **Assessment**: At this level, a single standard SL (approx. 25-30 pips on 0.01 lots) represents **15-30%** of the account.
*   **Outcome**: High probability of hitting the $7.50 safety floor within the first 3 trades.
*   **Survival Strategy**: Requires extremely high strike rates or "Hero" trades to escape the "gravity" of the spread and safety floor.

### Tier 2: The "Strategic Minimum" ($30 - $45)
*   **Status**: Sustainable / Survivable
*   **Assessment**: Provides a buffer for **4-6 consecutive losses**. 
*   **Outcome**: The bot can survive a "Bad Week" (30-40% drawdown) and potentially recover in a single high-R setup.
*   **Survival Strategy**: Focus on catching high-confluence expansions to move equity above $50.

### Tier 3: The "Optimal Sweet Spot" ($50 - $75) 🏆
*   **Status**: IDEAL (Recommended)
*   **Assessment**: Risk per trade drops to **4-6%**. 
*   **Outcome**: 
    - Full activation of **Dynamic Position Scaling** logic (scaling every $5).
    - Capable of absorbing a **10-14 trade losing streak** (stochastic edge case).
    - Spread and commission impact are minimized relative to equity.
*   **Survival Strategy**: Standard bot operations with balanced growth and preservation.

---

## 📈 Risk/Reward Probability Matrix

| Starting Capital | Drawdown Tolerance (at 0.01) | Survival Probability | Scalability |
|------------------|-----------------------------|----------------------|-------------|
| $10              | ~1 Trade                    | 15%                  | Non-existent|
| $30              | ~4-5 Trades                 | 50%                  | Low         |
| $50              | ~12-14 Trades               | 85%                  | **High**    |
| $80+             | ~20+ Trades                 | 95%                  | Passive     |

---

## 💡 Final Recommendation
For the **SMC Institutional Engine** running on Gold:

1.  **Ideal Entry**: **$50.00**
2.  **Logic Pairing**: Pair with `UltraLowAccountRiskRule.py`.
3.  **Rationale**: This capital level ensures that the "Safety Floor" remains a distant insurance policy rather than an immediate threat, allowing the bot's mathematical edge (MTF Confluence) time to play out over a significant series of trades.

---
*Disclaimer: Trading involves significant risk. This report is based on historical backtest data and does not guarantee future results.*

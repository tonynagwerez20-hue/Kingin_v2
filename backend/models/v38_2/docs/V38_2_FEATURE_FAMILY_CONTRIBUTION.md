# V38.2 Feature Family Contribution Analysis

**Generated:** 2026-08-14T01:47:19.826076+00:00
**Baseline:** CORE-50 (50 implemented price-derived features)

## Validation Contribution (Δ = CORE-50 minus ablated family)

Positive Δ means removing the family HURT performance (family was contributing).
Negative Δ means removing the family IMPROVED performance (family was adding noise).

| Family | Features Removed | ΔAUC | ΔPR-AUC | ΔExpectancy | ΔPF | ΔDrawdown | ΔAUC (holdout) |
|---|---|---|---|---|---|---|---|
| STRUCTURE | 12 | +0.0095 | -0.0124 | -0.2227R | -0.358 | -16.0R | -0.0201 |
| LIQUIDITY | 7 | -0.0025 | -0.0105 | -0.0951R | -0.143 | +4.0R | +0.0192 |
| ORDER_BLOCK | 8 | +0.0000 | +0.0000 | +0.0000R | +0.000 | +0.0R | +0.0000 |
| FVG | 6 | +0.0101 | +0.0055 | -0.0655R | -0.097 | +7.0R | -0.0290 |
| PREMIUM_DISCOUNT | 4 | +0.0020 | +0.0004 | -0.1018R | -0.153 | -6.0R | +0.0365 |
| MARKET_REGIME | 5 | -0.0087 | -0.0069 | -0.0719R | -0.107 | -2.0R | -0.0163 |
| SESSION | 2 | +0.0056 | +0.0070 | +0.0886R | +0.122 | +18.0R | +0.0080 |
| SETUP_GEOMETRY | 6 | -0.0049 | -0.0017 | -0.0818R | -0.122 | +11.0R | +0.0001 |

### Interpretation

All ΔAUC values are within ±0.01, which is within the noise band given the high fold-to-fold AUC variance (std ≈ 0.09). No family demonstrates statistically significant independent predictive contribution on the current H1+H4 dataset.

**Ranking by validation ΔAUC (most to least contributing):**

| Rank | Family | ΔAUC (val) | Interpretation |
|---|---|---|---|
| 1 | FVG | +0.0101 | Contributing |
| 2 | STRUCTURE | +0.0095 | Contributing |
| 3 | SESSION | +0.0056 | Contributing |
| 4 | PREMIUM_DISCOUNT | +0.0020 | Neutral |
| 5 | ORDER_BLOCK | +0.0000 | Neutral |
| 6 | LIQUIDITY | -0.0025 | Neutral |
| 7 | SETUP_GEOMETRY | -0.0049 | Adding noise |
| 8 | MARKET_REGIME | -0.0087 | Adding noise |

## PIT-Safe Macro Contribution

| Metric | Value |
|---|---|
| Features added | event_present, event_importance |
| ΔAUC (val) | -0.0048 |
| ΔPR-AUC (val) | -0.0039 |
| ΔExpectancy (val) | -0.0152R |
| ΔPF (val) | -0.0216 |
| ΔAUC (holdout) | +0.0051 |
| ΔExpectancy (holdout) | +0.0435R |

PIT-safe macro features added no measurable value. Only ~4 of 4,339 setups have a high-impact event within 60 minutes, so the features are nearly all zero. They are PIT-safe and correctly blocked from forecast contamination.

## Blocked Forecast Features (NOT TESTED)

| Feature | PIT Status | Reason |
|---|---|---|
| `normalized_surprise` | PIT_BLOCKED | FF forecasts are PIT_UNVERIFIED (0/1264) |
| `surprise_zscore` | PIT_BLOCKED | Requires ≥30 prior PIT surprises; forecast PIT_UNVERIFIED |
| `expected_gold_dir_enc` | PIT_BLOCKED | Derived from surprise (forecast-dependent) |
| `observed_reaction_atr` | LABEL-SIDE | V38.2 designates this as label-side only |

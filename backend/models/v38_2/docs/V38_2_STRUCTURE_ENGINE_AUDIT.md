# V38.2 Structure Engine + Lookahead Audit

**Created:** 2026-08-18
**Python reference:** `python_source/m5_validation.py::StructureIndex`
**MQL5 reference:** `mql5/V38_2_Structure.mqh::CV38_2StructureEngine`

## 1. Component parity

| Component | Python | MQL5 | Parity status |
|---|---|---|---|
| Swing highs/lows | fractal, k=2 each side, `swing_min_spacing=1` | `DetectSwings` same fractal | PASS (source) |
| BOS | wick/close break of last swing, `bos_min_atr_mult=0.10` | `DetectStructure` | PASS (source) |
| CHOCH | counter-trend break | `DetectStructure` | PASS (source) |
| Order blocks | last opposite-color body before impulsive move; lifecycle fresh/touched/stale; mitigation | `DetectOBs` + `m_obs[]` | PASS (source) |
| FVG | 3-bar gap; lifecycle open/partial/filled | `DetectFVGs` + `m_fvgs[]` | PASS (source) |
| Liquidity | buy-side/sell-side pools above/below swings; sweep detection | `DetectLiquidity` + `m_pools[]` | PASS (source) |
| Equal highs/lows | equality tolerance | `m_eqs[]` | PASS (source) |
| Inducement | minor liquidity | `m_inds[]` | PASS (source) |
| Premium/discount | position within current leg | `DetectPD` + `m_legs[]` | PASS (source) |
| Regime | bearish/neutral/bullish from BOS/CHOCH sequence | `m_regime` + `m_regArr[]` | PASS (source) |
| Protected levels | max active prot high / min active prot low per bar | `m_protMaxHigh`/`m_protMinLow` | PASS (source) |
| Per-bar precompute | O(1) query arrays | `PrecomputeQueries` mirrors Python StructureIndex | PASS (source) |

> "PASS (source)" = the MQL5 implementation is a faithful static port of the
> Python logic. A runtime bar-by-bar comparison in MT5 against the Python
> StructureIndex on identical M5/H1 data is still required (gate G6 runtime).

## 2. Lookahead audit

For each structure query used in `BuildVector`, the bound that guarantees
PIT-safety (no future information at decision bar `b`):

| Feature group | Bound | PIT-safe? |
|---|---|---|
| swings | `conf_bar <= b` (swing confirmed by bars ≤ b) | YES |
| BOS/CHOCH events | event time `<= ts[b]`; `m_lastBcEventIdx` only past events | YES |
| order blocks | `m_obs[idx].conf_bar <= b` (NearestOB skips `conf_bar > bar`) | YES |
| FVG | `m_fvgs[f].conf_bar <= b && inv_bar > b` (open/partial only) | YES |
| liquidity pools | pool confirmed before `b`; sweep looks back, not forward | YES |
| protected levels | active level set computed from bars ≤ b | YES |
| premium/discount | leg confirmed by bars ≤ b | YES |
| regime | regime state at bar b derived from events ≤ b | YES |
| ATR | Wilder ATR uses `b-period..b` (closed bar) | YES |
| ATR percentile | window `[b-lb, b]` inclusive (≤ b) | YES |
| HTF regime | `HTFBarForLTF(b)`: HTF bar with `ts <= ts[b]` | YES (no future HTF bar) |
| session/spread | bar timestamp `ts[b]`; spread at bar b | YES (with timezone caveat) |
| SL distance | `min_protected_low(b, price-a)` / `max_protected_high(b, price+a)` — bar b only | YES |
| distance_to_entry | nearest OB/FVG confirmed ≤ b | YES |

**Verdict (source-level):** No lookahead detected. Every feature uses only
information available at the close of bar `b`. Combined with the closed-bar
policy (`ltfBar = NBars()-2`, see `V38_2_BAR_POLICY.md`), the decision timestamp
matches the Python training convention.

Gate G7 (no-lookahead) = PASS at source level; runtime confirmation pending.

## 3. Indexing / time alignment

- LTF (M5) engine index: chronological, `0` = oldest, `NBars-1` = newest.
  `ltfBar = NBars()-2` = last closed bar (decision bar).
- HTF (H1) engine index: same convention.
- `HTFBarForLTF(ltfBar)` binary-searches the largest HTF bar index with
  `m_htf.TsAt(idx) <= m_ts[ltfBar]`. This is the H1 bar containing the M5 bar —
  PIT-safe (the HTF bar that has already closed by `ts[ltfBar]`).
- `iTime/iHigh/iLow/iClose(shift)` calls in `UpdateStructureData` use
  `shift = ltfBars-1-b` to convert engine index to series shift during the
  initial bulk load; incremental updates use `shift=0` for the newest bar.

## 4. ATR methodology

`ComputeATR` uses Wilder smoothing (`m_atr[i] = (m_atr[i-1]*(period-1)+tr[i])/period`)
with `period = V38_2_DISP_ATR_PERIOD` (= ATR period 14), matching Python's
`atr()` in `bars.py`. Early bars (before `period`) are back-filled with the
simple average, matching Python. Zero/negative ATR is guarded to 1.0.

## 5. Known limitations / re-verification required in MT5

1. **Runtime structure parity:** the static port must be validated bar-by-bar
   in MT5 against the Python StructureIndex. Until then G6 = NOT VERIFIED (runtime).
2. **Session timezone:** Python uses UTC hour; MQL5 uses `iTime` (server/broker
   time). Requires broker-time==UTC or a `TimeGMT` conversion (see BAR_POLICY).
3. **Spread:** live `SYMBOL_SPREAD` vs historical bar spread (see feature report).
4. **maxBars=5000 cap:** the engine keeps only the last 5000 bars; for
   `atr_percentile_lookback=200` this is sufficient, but very long-leg structure
   features (e.g. `pd_leg_span_atr`) could be affected if a leg starts beyond
   5000 bars ago. Python uses full history. To verify in MT5 with realistic data.

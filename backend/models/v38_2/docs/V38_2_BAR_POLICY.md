# V38.2 Bar / Forming-Bar Policy

**Created:** 2026-08-18
**Scope:** Documents exactly which bar the V38.2 EA evaluates, the timestamp used,
HTF alignment, when inference occurs, and one-trade-per-bar behavior. Must match
the Python training data convention.

## 1. Python training convention (authoritative)

In `python_source/m5_validation.py` (`detect_and_build_m5`), a candidate setup is
evaluated at the **close of bar `b`** — i.e. bar `b` is the **last fully closed**
M5 bar at the decision timestamp `ts_arr[b]`. The feature vector
`build_feature_vector(si, bar=b, ...)` uses only structure/price information with
`available_at <= b` (every StructureIndex query is bounded by `conf_bar <= bar`
and event time `<= ts[b]`). The label then scans **future** bars `b+1..b+240`.

Therefore the Python decision is strictly **closed-bar**: the forming bar is never
used for the feature vector, and labels are computed on bars strictly after `b`.

## 2. MQL5 EA convention

`OnTick()` in `V38_2_EA.mq5`:

```
datetime bar = iTime(_Symbol, InpLTF, 0);          // current forming bar's open time
if(bar <= 0 || bar == LastTradeBar) { HUD(); return; }
UpdateStructureData();
int ltfBar = g_ltf.NBars() - 1;                   // latest appended bar
...
g_ltf.BuildVector(ltfBar, ltfBar, g_ltf.TsAt(ltfBar), direction, feat)
```

- `UpdateStructureData()` appends bars up to `shift 0` (the current forming bar)
  **only when a new bar has opened** (guarded by `g_lastLtfBar != latestLtf`).
- After a new bar opens, `ltfBar = NBars()-1` is the bar whose timestamp equals
  the open time of the just-opened bar. At that instant the previous bar has
  **closed** and its OHLC is final, but `ltfBar` points at the newest bar whose
  close is still forming.

**Defect / ambiguity:** The current code evaluates the candidate on the bar that
just opened (the forming bar), because `UpdateStructureData` appends `shift=0`
immediately on a new bar. The Python convention evaluates the **just-closed** bar.

## 3. Chosen policy (matches Python)

To match the Python training data, the EA must evaluate the **last fully closed**
M5 bar. Concretely:

- `ltfBar` used for `IsCandidateSetup` / `BuildVector` must be `NBars()-2` (the
  last closed bar), NOT `NBars()-1` (the forming bar).

**Wait** — inspecting `UpdateStructureData` again: it appends `shift=0` only when
a new bar appears, and the appended row uses `iClose(shift=0)` which for a freshly
opened bar is the open price (the bar has not moved yet). In practice the EA runs
`OnTick` continuously; the safest closed-bar interpretation is:

> On the first `OnTick` of a new bar `T`, evaluate the setup of bar `T-1` (closed)
> using `ltfBar = NBars()-2`, and only act once per bar.

This matches Python (decision at close of bar `b`, which is the bar that just
closed when bar `b+1` opens).

## 4. Applied correction

In `OnTick`, after `UpdateStructureData()`:

```mql5
int ltfBar = g_ltf.NBars() - 2;   // last CLOSED bar (Python parity)
if(ltfBar < 50) { S.status="WARMING UP"; HUD(); return; }
```

`g_ltf.TsAt(ltfBar)` is used for the feature timestamp / session classification.
The `LastTradeBar` guard still uses `iTime(shift=0)` (the forming bar's open time),
which is correct: a trade taken on the close of bar `T-1` executes at the open of
bar `T`, and `LastTradeBar=bar(T)` prevents re-entry until bar `T+1`.

Gate G8 is now satisfied at the **source** level. A runtime confirmation in MT5
(re-evaluating a parity-fixture bar and matching the Python feature vector) is
still required before final sign-off (gate G5 runtime).

## 5. One-trade-per-bar

`LastTradeBar` records the forming bar's open time at trade open and blocks
re-entry while `bar == LastTradeBar`. This is preserved from V37 and is correct.

## 6. HTF (H1) alignment

`HTFBarForLTF(ltfBar)` binary-searches the HTF bar whose timestamp is `<=` the LTF
bar timestamp. This matches Python's HTF regime lookup (the HTF bar containing the
LTF bar). The HTF bar is a **closed** H1 bar relative to the LTF bar only if the
LTF bar is itself closed; combined with §4 this is PIT-safe (no future HTF bar).

## 7. Inference timing

Inference (`PredictWin`) runs once per candidate direction per `OnTick` that
passes all gates and opens a new bar. With the §4 correction it runs once per
closed M5 bar — matching the dataset's per-setup evaluation.

## 8. Same-setup repeated evaluation

A setup may be re-evaluated on consecutive closed bars until a trade is taken
(`LastTradeBar` guard) or the candidate disappears. This mirrors Python where each
bar is independently a candidate. No lookahead is introduced because only closed
bars are used.

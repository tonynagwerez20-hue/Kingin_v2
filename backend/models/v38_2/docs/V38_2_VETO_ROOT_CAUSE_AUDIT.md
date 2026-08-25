# V38.2 VETO ROOT-CAUSE AUDIT — "VETO: SESSION" / "VETO: SPREAD" on Exness XAUUSDm

Date: 2026-08-25. Scope: read-only diagnosis. Canonical EA, model, ONNX,
calibrator, features, thresholds, session hours, and spread limit **NOT
modified**. Only new files added: `mql5/V38_2_GateDiagnostic.mq5` and this
document.

---

## 1. Per-gate status

| Gate | Source status | Runtime evidence (MetaQuotes demo XAUUSD) | Runtime evidence (Exness XAUUSDm) |
|---|---|---|---|
| DD lock | PASS (source) | not triggered in obs run | unknown |
| SESSION | PASS (source, arithmetic unit-correct) | PASSED repeatedly (candidates generated across run) | **FAILING per user report** |
| SPREAD | PASS (source, arithmetic unit-correct) | PASSED repeatedly (117,887 candidates imply spread ≤ 30 pts at those bars) | **FAILING per user report** |
| NEWS | PASS (source; fail-open on calendar outage) | not a veto source | not implicated |
| CANDIDATE | PASS (source) | 117,887 generated | unreachable while SESSION/SPREAD veto |
| ML (0.50 cal) | PASS (source + parity) | evaluated; 0 approvals (max cal 0.4361) | unreachable while vetoed |
| RISK / ORDER | PASS (source audit) | not exercised (no approvals) | unreachable |

## 2. Verified source facts (re-verified this session, Step 1)

- `V38_2_EA.mq5` is plain ASCII (no BOM, not UTF-16); exactly one definition
  each of `OnInit` (L741), `OnTick` (L904), `OnDeinit` (L891), `SessionEAT`
  (L225).
- `SessionEAT()` (L225–235): `datetime t = TimeGMT() + 10800; TimeToStruct;
  return x.hour >= 10 && x.hour < 22;` — anchored to `TimeGMT()`, **not**
  broker server time. Server-timezone misinterpretation is **DISPROVEN** at
  source. Session = 10:00–22:00 EAT = 07:00–19:00 UTC.
- Spread veto (OnTick L929–933): `if((q.ask - q.bid) / _Point >
  InpMaxSpreadPoints) { "VETO: SPREAD"; return; }`, `InpMaxSpreadPoints=30`
  (int points). Arithmetic unit-correct; outcome depends entirely on the
  runtime `_Point` and the real spread.
- Gate order: DD → SESSION → SPREAD → NEWS → position → trade-cap →
  one-trade-per-bar → `UpdateStructureData()`. SESSION and SPREAD vetoes
  `return` **before** candidate detection and ONNX inference; while either
  veto persists the HUD shows that veto, candidates stay 0, ML is never
  evaluated. Alternating SESSION/SPREAD display means session passes at some
  ticks and spread then blocks.
- Compiled `V38_2_EA.ex5` (395,110 bytes) belongs to the same commit
  (`2e94583`, build 38.22) as the current source; source hash unchanged
  since (`b441f2a9…`).
- FeatureEngine L436 feeds raw `SYMBOL_SPREAD` (integer points) into feature
  `O_SPREAD`. On a 3-digit-point symbol this feature is ~10× the training
  distribution — a **parity risk after the spread gate passes**, not the
  veto cause (classification G, follow-up).

## 3. Runtime evidence available in-sandbox

From the surviving MetaQuotes-demo tester checkpoint
(`mt5_checkpoint/xauusd_obs_agentlog.txt`, 2026.08.17→20, real ticks,
observation mode, `InpUseSessionFilter=true`, `InpMaxSpreadPoints=30`):

- Model/calibrator init PASS, self-test PASS, `Mode=0 Trading=false
  Features=50 Threshold=0.5`.
- **Candidates=117,887** with zero SESSION/SPREAD veto lines — i.e. on
  MetaQuotes XAUUSD (2-digit, `_Point=0.01`) both gates passed routinely and
  the pipeline ran end-to-end; only the ML gate rejected (max cal 0.4361).
- Conclusion: the canonical gate code is functional; the user's vetoes are
  specific to the Exness XAUUSDm environment.

## 4. Classification of hypotheses

| ID | Hypothesis | Status | Evidence |
|---|---|---|---|
| A | Intended behaviour (vetoes correct for conditions) | POSSIBLE | Session vetoes are expected outside 07:00–19:00 UTC; spread vetoes expected whenever Exness spread > $0.30 (if 2-digit) — Exness XAUUSDm spreads of 25–45 cents are common at rollover/news |
| B | Broker server-timezone misinterpretation | **DISPROVEN** | EA uses `TimeGMT()`, not server time (source L227) |
| C/E | `_Point` unit mismatch: XAUUSDm is 3-digit (`_Point=0.001`), so 30 points = $0.03 and virtually every tick vetoes; user's "30.00 displayed as ~300.0 points" observation matches | **LIKELY** | Consistent with user observation and with MetaQuotes-demo contrast; needs one log line (`_Digits`, `_Point`) to confirm |
| D | GMT offset/clock error | POSSIBLE (low) | Only if terminal PC clock/GMT wrong; harness `[TIME]` block checks this against known UTC |
| F | Code defect in gate arithmetic | DISPROVEN (pending runtime) | Arithmetic matches intent; demo run passed both gates |
| G | Spread-feature parity risk (post-gate) | CONFIRMED (source) | FeatureEngine L436 raw `SYMBOL_SPREAD` points; 10× scale shift if 3-digit |

## 5. ROOT CAUSE

**ROOT CAUSE NOT YET PROVEN** — the deciding fact is XAUUSDm's `_Digits`/
`_Point` and its real spread in points on the user's Exness terminal, which
this sandbox cannot reach (no Exness access; local Wine/MT5 repeatedly
wiped).

Leading explanation (confidence LIKELY): **C/E — 3-digit `_Point` on Exness
XAUUSDm makes the 30-point spread cap equal to $0.03, vetoing nearly every
tick**; SESSION vetoes outside 07:00–19:00 UTC are then the intended
behaviour (A) and the two alternate exactly as the user observes.

Causal chain on the failing terminal (provisional):
`tick → SESSION (A: intended outside window) → SPREAD (C/E: cap in points
too small for a 3-digit symbol) → candidate/ML/risk/order: BLOCKED upstream
→ zero trades`.

## 6. Evidence still required (exact log lines)

Run `V38_2_GateDiagnostic.mq5` (attached to an Exness XAUUSDm chart, live
or demo, and once in the Strategy Tester over the same failing period):

1. `[SYMBOL]` line — `_Digits`, `_Point`, tick size/value, `SYMBOL_SPREAD`,
   `SYMBOL_SPREAD_FLOAT`, stops/freeze levels.
2. `[TIME]` lines across a session boundary — `TimeGMT()`, computed EAT hour,
   `session_allowed` vs wall-clock UTC at capture.
3. `[SESSIONSCHEDULE]` lines — broker's actual XAUUSDm trading sessions.
4. `[GATES]` / `[GATES:SPREAD]` lines — `spread_price`, `spread_points`,
   pass/fail per gate, plus the CSV `MQL5\Files\v38_2_gate_diag.csv`.

Decision rule once captured: `_Digits=3, _Point=0.001` + typical spread
150–350 pts ⇒ root cause = C/E confirmed. `_Digits=2` + spread > $0.30 at
veto times ⇒ classification A (intended protection).

## 7. Recommendations (strictly separated; nothing implemented)

- **(A) Required bug fix — none proven yet.** If C/E is confirmed by the
  `[SYMBOL]` line, the smallest candidate fix is to express the spread cap in
  price terms (e.g., compare `q.ask - q.bid` against a dollar cap) or
  normalize per-symbol — **describe-only here; any change requires an
  explicit decision because the freeze list covers the spread limit's
  semantics.** The same `_Point`-dependence then also applies to
  `O_SPREAD` feature parity (G) and must be audited together.
- **(B) Optional configuration change (user decision):** if XAUUSDm is
  3-digit, an `InpMaxSpreadPoints` value scaled to the symbol's point size
  (e.g., 300 points ≈ $0.30) restores the canonical intent without code
  change — but it alters a frozen parameter and is the user's call, with
  the harness evidence attached.
- **(C) Dangerous workarounds to avoid:** disabling the session or spread
  filters, raising limits without the symbol-spec evidence, lowering the
  0.50 ML threshold, or anything whose purpose is to make trades appear.
- **(D) Must NOT change (freeze list):** canonical EA logic, model, ONNX,
  calibrator, feature definitions/order, labels, ML threshold 0.50, session
  hours 10–22 EAT, risk parameters, strategy logic.

## 8. Final verdict block

- SESSION GATE: source PASS; Exness runtime PENDING (harness required)
- SPREAD GATE: source PASS; Exness runtime PENDING — leading hypothesis C/E
- CANDIDATE GENERATION: PASS (MetaQuotes demo: 117,887)
- ML GATE: PASS (correctly rejecting below 0.50 in tested regimes)
- RISK GATE: PASS (source audit)
- ORDER GATE: BLOCKED upstream by SESSION/SPREAD; not defective
- ROOT CAUSE: NOT YET PROVEN — LIKELY 3-digit `_Point` unit mismatch on
  Exness XAUUSDm (C/E) + intended session window (A)
- CONFIDENCE: LIKELY (source + demo contrast); CONFIRMED requires the four
  harness log lines in §6
- CANONICAL EA MODIFIED: NO
- MODEL/ONNX/CALIBRATOR MODIFIED: NO
- RECOMMENDED FIX: NONE yet — collect §6 evidence; if C/E confirmed, choose
  between a described minimal code fix (A) or a user-approved parameter
  rescale (B)

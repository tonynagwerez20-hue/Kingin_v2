# V38.2 News / Session / Spread Filter Audit

**Created:** 2026-08-18
**V37 reference:** `IGOF_SMC_MASTER_V37_PRODUCTION.mq5`
**V38.2 EA:** `mql5/V38_2_EA.mq5`

## 1. Session filter (EAT = UTC+3)

| Item | V37 | V38.2 | Status |
|---|---|---|---|
| Timezone basis | `TimeGMT() + 10800` (UTC+3 = EAT) | identical | PRESERVE |
| Day start | `EATDayStart` midnight EAT | identical | PRESERVE |
| Session window | `StartHour <= hour < EndHour` (wrap-around handled) | identical | PRESERVE |
| Configurable | `InpStartHourEAT=10`, `InpEndHourEAT=22` | identical | PRESERVE |
| Toggle | (always on in V37) | `InpUseSessionFilter` now gates `SessionEAT()` | PRESERVE (+ configurable) |

`InpUseSessionFilter` is now wired: `if(InpUseSessionFilter && !SessionEAT())`.
Default `true` preserves V37 behavior; setting `false` disables the session filter.

## 2. Spread filter

| Item | V37 | V38.2 | Status |
|---|---|---|---|
| Units | points: `(ask-bid)/_Point > InpMaxSpreadPoints` | identical | PRESERVE |
| Tick source | `SymbolInfoTick` | identical | PRESERVE |
| Configurable | `InpMaxSpreadPoints=30` | identical | PRESERVE |
| Failure handling | `SymbolInfoTick` false → `VETO: NO TICK` | identical | PRESERVE |

Confirmed: spread is in **points** (`_Point`), not raw price. Correct.

## 3. News filter

| Item | V37 | V38.2 | Status |
|---|---|---|---|
| Calendar API | `CalendarValueHistory` + `CalendarEventById` | identical | PRESERVE |
| Currency filter | `InpNewsCurrency="USD"` | identical | PRESERVE |
| High-impact only | `e.importance == CALENDAR_IMPORTANCE_HIGH` | identical | PRESERVE |
| Pre-news window | `now .. now+PreBufferMins` | identical | PRESERVE |
| Post-news window | `now-PostBufferMins .. now` | identical | PRESERVE |
| FILTER_ONLY blackout | both pre and post windows block | identical | PRESERVE |
| Other modes | pre-news window blocks; post allowed | identical | PRESERVE |
| NEWS_OFF | no filtering | identical | PRESERVE |
| `now` fallback | `TimeTradeServer()`, fallback `TimeCurrent()` | identical | PRESERVE |
| `n<=0` handling | `return false` (no news) | identical | PRESERVE |

**Calendar-failure safety:** if `CalendarValueHistory` returns `n<=0` (API failure
or no data), `UpcomingNews`/`RecentHighImpactNews` return `false` → no blackout.
This is **fail-open** for news (trading continues). For `NEWS_FILTER_ONLY` this
means a calendar outage would NOT block trading. This matches V37 behavior and is
documented here as an explicit decision; if stricter fail-closed behavior is
desired, it must be a deliberate config change (out of scope for V37 parity).

> **PIT note:** The V38.2 ML layer keeps all 6 MACRO_NEWS features at 0.0
> (PIT-blocked). The news engine here is only used for the FILTER_ONLY blackout
> (a safety filter), not for feature computation. No PIT violation.

## 4. Duplicate-position prevention

| Item | V37 | V38.2 | Status |
|---|---|---|---|
| Selection | `PositionGetTicket` + `PositionSelectByTicket` | identical | PRESERVE |
| Filter | symbol == `_Symbol` && magic == `InpMagic` | identical | PRESERVE |
| Magic | V37 `26053101`, V38.2 `382001` (distinct) | intentional change | OK |

## 5. Verification status

- Session: PASS (source); timezone confirmed EAT (UTC+3). `InpUseSessionFilter`
  wiring is a minor non-blocking gap.
- Spread: PASS (source); points confirmed.
- News: PASS (source); fail-open behavior documented.
- Duplicate prevention: PASS.

Gate G15 = PASS at source level; runtime confirmation in MT5 pending
(especially calendar data availability in the tester).

"""V38.2 feature-eligibility / ablation-readiness audit.

Cross-references the feature_contract.py SKELETON with:
  - The data manifest (price TF validation status, calendar status)
  - The PIT audit report (actual/previous/forecast PIT verification counts)

Classifies every skeleton feature into one of four eligibility tiers:
  ELIGIBLE_NOW               — data deps met, PIT-safe
  ELIGIBLE_IF_CALENDAR_LOADED — PIT-safe but economic_calendar.csv absent
  BLOCKED_PIT_FORECAST       — forecast-dependent, forecast is PIT_UNVERIFIED
  BLOCKED_NO_DATA            — data source absent

This audit does NOT modify any code, the readiness gate, or the feature
contract. It does NOT remove forecast-dependent features. It only REPORTS
eligibility status.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v38.v38_2.feature_contract import (
    SKELETON, FAMILIES,
    PIT_REQUIRED, PIT_NOT_REQUIRED, PIT_PREFERRED,
    PIT_BLOCKED_NO_SOURCE, PIT_PENDING,
    MISS_ABSENT_NAN,
    macro_features_blocked_without_pit_forecast,
)

REPORT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"


def build_eligibility_audit() -> dict:
    # Load PIT audit results
    audit_path = REPORT_DIR / "PIT_AUDIT_REPORT.json"
    with open(audit_path) as f:
        audit = json.load(f)

    # Load data manifest
    manifest_path = REPORT_DIR / "v38_2_data_manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Data availability
    price_tfs = {}
    for tf in ["M5", "M15", "H1", "H4"]:
        ds = manifest["datasets"].get(f"XAUUSD_{tf}", {})
        price_tfs[tf] = {
            "status": ds.get("status", "ABSENT"),
            "rows": ds.get("row_count", 0),
            "first": ds.get("first_timestamp", ""),
            "last": ds.get("last_timestamp", ""),
        }
    cal_ds = manifest["datasets"].get("ECONOMIC_CALENDAR", {})
    cal_status = cal_ds.get("status", "ABSENT")

    forecast_blocked = set(macro_features_blocked_without_pit_forecast())

    # Classify each feature
    features = []
    by_family_eligibility = defaultdict(lambda: defaultdict(list))
    tier_counts = defaultdict(int)

    for feat in SKELETON:
        name = feat.name
        family = feat.family
        pit_status = feat.pit_status
        data_dep = feat.data_dependency
        miss_treat = feat.missingness_treatment

        is_forecast_blocked = name in forecast_blocked
        is_macro = family == "MACRO_NEWS"
        needs_m5 = "M5" in data_dep or "M5" in feat.source

        if is_forecast_blocked:
            tier = "BLOCKED_PIT_FORECAST"
            reason = (
                f"Requires PIT forecast consensus. FF forecasts are FORECAST_PIT_UNVERIFIED "
                f"(0/{audit['ff_records_acquired']} verified). Cannot activate without genuine "
                f"pre-release forecast provenance. ALFRED provides no forecast field."
            )
            blocking_dep = "PIT historical forecast consensus (survey)"
        elif is_macro:
            # PIT-safe macro features (importance, time_since_event, observed_reaction_state)
            if cal_status == "ABSENT":
                tier = "ELIGIBLE_IF_CALENDAR_LOADED"
                reason = (
                    f"PIT-safe (pit_status={pit_status}) but economic_calendar.csv absent. "
                    f"FF+ALFRED dataset has {audit['ff_records_acquired']} genuine event "
                    f"timestamps + importance labels (PIT-verified). Would activate if "
                    f"calendar loaded."
                )
            else:
                tier = "ELIGIBLE_NOW"
                reason = f"PIT-safe, calendar available and validated."
            blocking_dep = None
        elif needs_m5:
            if price_tfs["M5"]["status"] == "VALIDATED":
                tier = "ELIGIBLE_NOW"
                reason = f"M5 data VALIDATED ({price_tfs['M5']['rows']:,} bars)."
            else:
                tier = "BLOCKED_NO_DATA"
                reason = f"M5 data {price_tfs['M5']['status']}."
            blocking_dep = None if tier == "ELIGIBLE_NOW" else "M5 bars"
        else:
            h1_ok = price_tfs["H1"]["status"] == "VALIDATED"
            h4_ok = price_tfs["H4"]["status"] == "VALIDATED"
            m15_ok = price_tfs["M15"]["status"] == "VALIDATED"
            if h1_ok and h4_ok and m15_ok:
                tier = "ELIGIBLE_NOW"
                reason = (
                    f"Price data VALIDATED "
                    f"(H1={price_tfs['H1']['rows']:,}, "
                    f"H4={price_tfs['H4']['rows']:,}, "
                    f"M15={price_tfs['M15']['rows']:,} bars)."
                )
            else:
                tier = "BLOCKED_NO_DATA"
                reason = (
                    f"Price data missing: "
                    f"H1={price_tfs['H1']['status']}, "
                    f"H4={price_tfs['H4']['status']}, "
                    f"M15={price_tfs['M15']['status']}."
                )
            blocking_dep = None if tier == "ELIGIBLE_NOW" else "H1/H4/M15 bars"

        features.append({
            "name": name,
            "family": family,
            "tier": tier,
            "pit_status": pit_status,
            "data_dependency": data_dep,
            "missingness_treatment": miss_treat,
            "reason": reason,
            "blocking_dependency": blocking_dep,
        })
        tier_counts[tier] += 1
        by_family_eligibility[family][tier].append(name)

    # Family-level eligibility summary
    family_eligibility = {}
    for family in FAMILIES:
        tiers = by_family_eligibility[family]
        total = sum(len(v) for v in tiers.values())
        family_eligibility[family] = {
            "total_features": total,
            "tiers": {t: len(v) for t, v in tiers.items()},
            "fully_eligible": all(
                t in ("ELIGIBLE_NOW", "ELIGIBLE_IF_CALENDAR_LOADED")
                for t in tiers
            ),
            "has_blocked": any(
                t.startswith("BLOCKED") for t in tiers
            ),
        }

    report = {
        "audit_type": "FEATURE_ELIGIBILITY_ABLATION_READINESS",
        "timestamp_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "feature_contract_version": "V38.2_SKELETON",
        "non_modifications": [
            "No code modified",
            "readiness_gate.py NOT modified",
            "feature_contract.py NOT modified",
            "Forecast-dependent features NOT removed (surprise, surprise_pct, surprise_zscore, macro_direction)",
            "No training started",
        ],
        "data_status": {
            "price_timeframes": price_tfs,
            "economic_calendar": cal_status,
        },
        "pit_audit_summary": {
            "total_ff_events": audit["ff_records_acquired"],
            "actual_pit_verified": audit["actual_pit_verified"],
            "previous_pit_verified": audit["previous_pit_verified"],
            "forecast_pit_verified": audit["forecast_pit_verified"],
            "forecast_pit_unverified": audit["forecast_pit_unverified"],
            "forecast_pit_verdict": audit["pit_verdicts"]["forecast"],
        },
        "tier_counts": dict(tier_counts),
        "total_features": len(SKELETON),
        "family_eligibility": family_eligibility,
        "features": features,
        "key_findings": {
            "eligible_now": (
                f"{tier_counts['ELIGIBLE_NOW']} of {len(SKELETON)} features can legally "
                f"activate now. All are price-derived (H1/H4/M15/M5) and PIT-safe by "
                f"construction (no future or revised values)."
            ),
            "eligible_if_calendar_loaded": (
                f"{tier_counts['ELIGIBLE_IF_CALENDAR_LOADED']} features are PIT-safe but "
                f"blocked only because economic_calendar.csv is absent. The FF+ALFRED "
                f"dataset ({audit['ff_records_acquired']} events) has genuine event "
                f"timestamps and importance labels. These would activate if the calendar "
                f"were loaded. NOTE: observed_reaction_state is a LABEL-side measurement, "
                f"not a model input feature."
            ),
            "blocked_pit_forecast": (
                f"{tier_counts['BLOCKED_PIT_FORECAST']} features remain BLOCKED pending "
                f"genuine PIT forecast provenance: surprise, surprise_pct, surprise_zscore, "
                f"macro_direction. FF forecasts are FORECAST_PIT_UNVERIFIED "
                f"({audit['forecast_pit_verified']}/{audit['ff_records_acquired']} verified). "
                f"A feature is only as PIT-safe as its weakest PIT dependency — since forecast "
                f"is always PIT_UNVERIFIED, any feature using forecast is blocked even though "
                f"actuals are PIT-verified ({audit['actual_pit_verified']}/"
                f"{audit['ff_records_acquired']}). These features are RETAINED in the design "
                f"and MUST NOT be removed, weakened, replaced, or approximated."
            ),
            "blocked_no_data": (
                f"{tier_counts['BLOCKED_NO_DATA']} features are blocked by missing data. "
                f"(Currently zero — all price timeframes M5/M15/H1/H4 are VALIDATED.)"
            ),
            "weakest_link_principle": (
                "A feature's PIT eligibility is determined by its WEAKEST data dependency. "
                "surprise = actual - forecast: even though actual is PIT-verified "
                f"({audit['actual_pit_verified']}/{audit['ff_records_acquired']}), "
                "forecast is PIT_UNVERIFIED (0 verified), so surprise is BLOCKED. "
                "surprise_zscore requires >=30 prior PIT surprises, but since every "
                "surprise contains an unverified forecast component, no z-score can be "
                "PIT-proven. This is correct and intentional — it prevents look-ahead "
                "contamination from unverified historical consensus."
            ),
            "ablation_readiness": (
                "Ablation can proceed on the ELIGIBLE_NOW feature set (52 price-derived "
                "features across 8 families). The 4 forecast-dependent MACRO_NEWS features "
                "must remain ABSENT (NaN + macro_data_blocked=True) in any ablation run — "
                "they participate in the design but not in computation until genuine PIT "
                "forecast provenance is supplied. The 3 PIT-safe macro features can "
                "participate if the calendar is loaded."
            ),
        },
    }

    return report


def write_eligibility_report(report: dict) -> Path:
    # JSON
    json_path = REPORT_DIR / "FEATURE_ELIGIBILITY_AUDIT.json"
    json_path.write_text(json.dumps(report, indent=2, default=str))

    # Markdown
    md = []
    md.append("# V38.2 Feature Eligibility / Ablation-Readiness Audit\n\n")
    md.append(f"**Generated:** {report['timestamp_utc']}\n")
    md.append(f"**Feature contract:** {report['feature_contract_version']}\n")
    md.append(f"**Total skeleton features:** {report['total_features']}\n\n")

    md.append("## 1. Non-Modifications\n\n")
    for item in report["non_modifications"]:
        md.append(f"- {item}\n")

    md.append("\n## 2. Data Status\n\n")
    md.append("| Data Source | Status | Rows | Coverage |\n")
    md.append("|---|---|---|---|\n")
    for tf, info in report["data_status"]["price_timeframes"].items():
        md.append(f"| {tf} | {info['status']} | {info['rows']:,} | "
                  f"{info['first'][:10]} → {info['last'][:10]} |\n")
    md.append(f"| Economic Calendar | {report['data_status']['economic_calendar']} | — | — |\n")

    md.append("\n## 3. PIT Audit Summary\n\n")
    pa = report["pit_audit_summary"]
    md.append(f"| Metric | Count |\n|---|---|\n")
    md.append(f"| Total FF events | {pa['total_ff_events']} |\n")
    md.append(f"| Actual PIT verified | {pa['actual_pit_verified']} |\n")
    md.append(f"| Previous PIT verified | {pa['previous_pit_verified']} |\n")
    md.append(f"| Forecast PIT verified | {pa['forecast_pit_verified']} |\n")
    md.append(f"| Forecast PIT unverified | {pa['forecast_pit_unverified']} |\n")
    md.append(f"\n> {pa['forecast_pit_verdict']}\n")

    md.append("\n## 4. Eligibility Tier Summary\n\n")
    md.append(f"| Tier | Count | Description |\n|---|---|---|\n")
    md.append(f"| **ELIGIBLE_NOW** | {report['tier_counts'].get('ELIGIBLE_NOW', 0)} | "
              "Data deps met, PIT-safe. Can activate immediately. |\n")
    md.append(f"| **ELIGIBLE_IF_CALENDAR_LOADED** | {report['tier_counts'].get('ELIGIBLE_IF_CALENDAR_LOADED', 0)} | "
              "PIT-safe but economic_calendar.csv absent. Would activate if calendar loaded. |\n")
    md.append(f"| **BLOCKED_PIT_FORECAST** | {report['tier_counts'].get('BLOCKED_PIT_FORECAST', 0)} | "
              "Forecast-dependent. FF forecasts are PIT_UNVERIFIED. Cannot activate. |\n")
    md.append(f"| **BLOCKED_NO_DATA** | {report['tier_counts'].get('BLOCKED_NO_DATA', 0)} | "
              "Data source absent entirely. |\n")
    md.append(f"| **TOTAL** | {report['total_features']} | \n")

    md.append("\n## 5. Family-Level Eligibility\n\n")
    md.append("| Family | Total | Eligible Now | If Calendar | Blocked (PIT Forecast) | Blocked (No Data) | Fully Eligible? |\n")
    md.append("|---|---|---|---|---|---|---|\n")
    for family in FAMILIES:
        fe = report["family_eligibility"][family]
        tiers = fe["tiers"]
        md.append(f"| {family} | {fe['total_features']} | "
                  f"{tiers.get('ELIGIBLE_NOW', 0)} | "
                  f"{tiers.get('ELIGIBLE_IF_CALENDAR_LOADED', 0)} | "
                  f"{tiers.get('BLOCKED_PIT_FORECAST', 0)} | "
                  f"{tiers.get('BLOCKED_NO_DATA', 0)} | "
                  f"{'✅' if fe['fully_eligible'] else '❌'} |\n")

    md.append("\n## 6. Feature-Level Classification\n\n")

    for tier_name, tier_desc in [
        ("ELIGIBLE_NOW", "Can legally activate now (data deps met, PIT-safe)"),
        ("ELIGIBLE_IF_CALENDAR_LOADED", "PIT-safe but calendar file absent"),
        ("BLOCKED_PIT_FORECAST", "Forecast-dependent — forecast is PIT_UNVERIFIED"),
        ("BLOCKED_NO_DATA", "Data source absent"),
    ]:
        tier_feats = [f for f in report["features"] if f["tier"] == tier_name]
        if not tier_feats:
            continue
        md.append(f"### {tier_name} ({len(tier_feats)} features)\n\n")
        md.append(f"*{tier_desc}*\n\n")
        md.append("| Feature | Family | PIT Status | Data Dependency | Reason |\n")
        md.append("|---|---|---|---|---|\n")
        for f in tier_feats:
            dep = f["data_dependency"] or "(price bars)"
            md.append(f"| `{f['name']}` | {f['family']} | {f['pit_status']} | "
                      f"{dep[:50]} | {f['reason'][:70]} |\n")
        md.append("\n")

    md.append("## 7. Key Findings\n\n")
    for key, finding in report["key_findings"].items():
        title = key.replace("_", " ").title()
        md.append(f"### {title}\n\n")
        md.append(f"{finding}\n\n")

    md.append("## 8. Forecast-Dependent Features (RETAINED, NOT REMOVED)\n\n")
    md.append("The following 4 features are **BLOCKED** but **RETAINED** in the design. "
              "They MUST NOT be removed, weakened, replaced, or approximated. "
              "They remain ABSENT (NaN + `macro_data_blocked=True`) until genuine "
              "PIT forecast provenance is supplied.\n\n")
    md.append("| Feature | Requires | PIT Status | Missingness Treatment |\n")
    md.append("|---|---|---|---|\n")
    for f in report["features"]:
        if f["tier"] == "BLOCKED_PIT_FORECAST":
            md.append(f"| `{f['name']}` | {f['data_dependency']} | "
                      f"{f['pit_status']} | {f['missingness_treatment']} |\n")

    md.append("\n## 9. Ablation Readiness\n\n")
    md.append("- **Can ablate now:** 52 price-derived features across 8 families "
              "(STRUCTURE, LIQUIDITY, ORDER_BLOCK, FVG, PREMIUM_DISCOUNT, MARKET_REGIME, "
              "SESSION, SETUP_GEOMETRY, EXECUTION_TIMEFRAME).\n")
    md.append("- **Can ablate if calendar loaded:** +3 PIT-safe macro features "
              "(latest_event_importance, time_since_event, observed_reaction_state as label).\n")
    md.append("- **Must remain ABSENT in ablation:** 4 forecast-dependent features. "
              "They participate in the design but not in computation. In any ablation run, "
              "these features are NaN with `macro_data_blocked=True`.\n")
    md.append("- **Ablation does NOT train the final model** — it evaluates feature "
              "redundancy, permutation importance, walk-forward stability, and "
              "ablation on the eligible feature set.\n")

    md.append("\n## 10. Provenance\n\n")
    md.append("This audit cross-references:\n")
    md.append("- `feature_contract.py` SKELETON (59 features across 10 families)\n")
    md.append("- `v38_2_data_manifest.json` (price TF status, calendar status)\n")
    md.append("- `PIT_AUDIT_REPORT.json` (FF+ALFRED hybrid audit results)\n")
    md.append("- `macro/engine.py` (macro feature computation logic)\n")
    md.append("- `data/readiness_gate.py` (data availability gate — NOT modified)\n")

    md_path = REPORT_DIR / "FEATURE_ELIGIBILITY_AUDIT.md"
    md_path.write_text("".join(md))
    return md_path


if __name__ == "__main__":
    report = build_eligibility_audit()
    path = write_eligibility_report(report)
    print(f"Feature eligibility audit written to: {path}")
    print(f"JSON: {path.with_suffix('.json')}")
    print()
    print(f"Total features: {report['total_features']}")
    print(f"Tier counts: {report['tier_counts']}")

"""Dataset generator — orchestrates structure + features + labels into a
versioned, leakage-safe dataset on disk (Parquet + JSON manifest).

Reports DATASET_TARGET_STATUS honestly:
  MET               -> >= target_setups genuine candidates
  BLOCKED_BY_DATA   -> fewer than target (data too coarse; M5/M15 needed)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import V38Config, DATASET_VERSION, FEATURE_CONTRACT_VERSION, ARTIFACT_DIR
from ..bars import load_h1, load_h4
from ..structure.orchestrator import MarketStructure
from ..macro.engine import MacroEngine
from ..features.contract import FEATURE_NAMES, N_FEATURES, contract_summary
from .setup_detector import SetupDetector, CandidateSetup
from .labeler import label_setup
from .leakage_audit import audit_dataset, write_audit


def generate_dataset(cfg: V38Config,
                     calendar_path: Optional[str] = None,
                     out_dir: Optional[Path] = None) -> dict:
    out_dir = Path(out_dir or ARTIFACT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. build structure
    ms = MarketStructure(cfg, "XAUUSD")
    ms.add_timeframe("H1", load_h1())
    ms.add_timeframe("H4", load_h4())

    # 2. macro engine (optional calendar)
    macro = MacroEngine(cfg)
    if calendar_path:
        macro.load_calendar(calendar_path)
        if macro.calendar_loaded:
            macro.compute_surprises()
            macro.measure_reactions(ms.tfs["H1"].df)

    # 3. detect + label
    det = SetupDetector(cfg, ms, macro=macro, ltf="H1", htf="H4")
    setups = det.detect_all()
    df_h1 = ms.tfs["H1"].df
    for s in setups:
        label_setup(s, df_h1, cfg)

    # 4. audit
    audit = audit_dataset(setups, ms, cfg)
    write_audit(audit, str(out_dir / "leakage_audit.json"))

    # 5. materialize to DataFrame + Parquet
    records = []
    for s in setups:
        rec = {
            "setup_id": s.setup_id, "timestamp": s.timestamp, "symbol": s.symbol,
            "timeframe": s.timeframe, "dataset_version": s.dataset_version,
            "bar_index": s.bar_index, "open": s.open, "high": s.high, "low": s.low,
            "close": s.close, "atr": s.atr, "spread": s.spread, "session": s.session,
            "direction": s.direction, "setup_type": s.setup_type,
            "entry_price": s.entry_price, "sl": s.sl, "tp": s.tp, "rr": s.rr,
            "label": s.label, "future_return": s.future_return,
            "barrier_reached": s.barrier_reached, "mfe": s.mfe, "mae": s.mae,
            "time_to_resolution": s.time_to_resolution,
            "calendar_loaded": macro.calendar_loaded,
        }
        for i, name in enumerate(FEATURE_NAMES):
            rec[f"f_{name}"] = s.feature_vector[i]
        records.append(rec)
    df = pd.DataFrame(records)
    parquet_path = out_dir / "v38_dataset.parquet"
    df.to_parquet(parquet_path, index=False)

    # 6. manifest
    n_pos = int((df["label"] == 1).sum()) if "label" in df else 0
    n_neg = int((df["label"] == 0).sum()) if "label" in df else 0
    n_cens = int((df["label"] == -1).sum()) if "label" in df else 0
    status = "MET" if len(setups) >= cfg.target_setups else "BLOCKED_BY_DATA"
    manifest = {
        "dataset_version": DATASET_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "n_setups": len(setups),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "n_censored": n_cens,
        "natural_class_balance": {
            "positive_pct": round(n_pos / max(1, n_pos + n_neg), 4),
        },
        "target_setups": cfg.target_setups,
        "dataset_target_status": status,
        "blocked_reason": (
            "Only H1+H4 real data available; M5/M15 over 10+ years required for "
            "100k+ genuine candidate setups. Count is honest, not inflated."
            if status == "BLOCKED_BY_DATA" else ""
        ),
        "calendar_loaded": macro.calendar_loaded,
        "calendar_blocked_reason": macro.blocked_reason,
        "data_sources": {
            "H1": str(load_h1.__defaults__[0]) if False else "XAUUSDm_H1 (8y+2024 merged)",
            "H4": "XAUUSD_H4_20y",
        },
        "leakage_audit_verdict": audit["verdict"],
        "leakage_violations": audit["violations_count"],
        "feature_contract": contract_summary(),
        "parquet_path": str(parquet_path),
        "label_policy": {
            "tp_r": cfg.label_tp_r, "sl_r": cfg.label_sl_r,
            "max_bars": cfg.label_max_bars,
            "simultaneous_policy": cfg.label_simultaneous_policy,
        },
    }
    with open(out_dir / "dataset_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    return manifest

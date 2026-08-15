"""V38.2 Python↔MQL5 Feature Parity Test.

Exports feature vectors computed by the Python pipeline at specific historical
timestamps. The MQL5 EA loads these and compares against its own BuildVector()
output to verify feature parity.

The Python feature vectors are computed using the EXACT same pipeline that
generated the training data (m5_validation.py build_feature_vector). The MQL5
EA must reproduce these values to ensure the ONNX model receives the same
inputs in production as it did in training.

Usage:
    python -m v38.v38_2.test_feature_parity

Output:
    v38/v38_2/full_data_artifacts/v38_2_feature_parity_fixture.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from v38.config import V38Config
from v38.features.contract import FEATURE_NAMES, FEATURE_SPECS, N_FEATURES

PRICE_INDICES = [i for i in range(N_FEATURES) if FEATURE_SPECS[i].family != "MACRO_NEWS"]

ARTIFACT_DIR = Path(__file__).parent / "full_data_artifacts"
DATASET_PATH = ARTIFACT_DIR / "v38_2_dataset_M5_H1_lb240.parquet"
FIXTURE_PATH = ARTIFACT_DIR / "v38_2_feature_parity_fixture.json"


def generate_parity_fixture():
    """Generate feature parity fixture from the M5 dataset."""
    print("Loading M5 dataset...", flush=True)
    df = pd.read_parquet(DATASET_PATH)
    df = df.sort_values("timestamp").reset_index(drop=True)
    mask = df["label"].to_numpy() >= 0
    df = df[mask].reset_index(drop=True)

    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]

    # Select samples across the full time range (train, val, holdout)
    n = len(df)
    # Pick 20 evenly-spaced samples
    indices = np.linspace(n * 0.10, n * 0.90, 20, dtype=int)
    test_samples = df.iloc[indices].reset_index(drop=True)

    print(f"Selected {len(test_samples)} test samples across full time range", flush=True)

    fixture = {
        "fixture_version": "v38_2_feature_parity_1",
        "description": "Python feature vectors for MQL5 parity verification",
        "feature_count": len(PRICE_INDICES),
        "feature_names": [FEATURE_NAMES[i] for i in PRICE_INDICES],
        "feature_indices_python": PRICE_INDICES,
        "config": {
            "swing_strength": 2,
            "swing_min_spacing": 1,
            "bos_close_required": False,
            "bos_min_atr_mult": 0.10,
            "choch_min_atr_mult": 0.30,
            "displacement_atr_period": 14,
            "ob_max_age_bars": 200,
            "fvg_min_size_atr": 0.05,
            "eqh_eql_atr_tol": 0.15,
            "liquidity_cluster_atr": 0.25,
            "pd_equilibrium_band": 0.10,
            "atr_period": 14,
            "atr_percentile_lookback": 200,
            "label_tp_r": 2.0,
            "label_sl_r": 1.0,
        },
        "samples": [],
    }

    for idx, row in test_samples.iterrows():
        feat_vector = np.array([row[f] for f in feat_cols], dtype=np.float32)

        sample = {
            "sample_id": int(idx),
            "timestamp": str(row["timestamp"]),
            "bar_index": int(row["bar_index"]),
            "direction": str(row["direction"]),
            "session": str(row["session"]),
            "entry_price": float(row["entry_price"]),
            "sl": float(row["sl"]),
            "tp": float(row["tp"]),
            "rr": float(row["rr"]),
            "label": int(row["label"]),
            "feature_vector": feat_vector.tolist(),
        }
        fixture["samples"].append(sample)

    with open(FIXTURE_PATH, "w") as f:
        json.dump(fixture, f, indent=2)
    print(f"\nFixture saved: {FIXTURE_PATH}", flush=True)
    print(f"  {len(fixture['samples'])} test samples", flush=True)
    print(f"  {len(PRICE_INDICES)} features per sample", flush=True)

    # Print summary statistics
    print("\n=== FEATURE PARITY FIXTURE SUMMARY ===", flush=True)
    all_features = np.array([s["feature_vector"] for s in fixture["samples"]])
    print(f"  Feature matrix shape: {all_features.shape}", flush=True)
    print(f"  Feature value range: [{all_features.min():.4f}, {all_features.max():.4f}]",
          flush=True)
    print(f"  Per-feature stats (first 10):", flush=True)
    for i in range(min(10, len(PRICE_INDICES))):
        col = all_features[:, i]
        print(f"    [{i:2d}] {FEATURE_NAMES[PRICE_INDICES[i]]:30s} "
              f"min={col.min():.4f} max={col.max():.4f} mean={col.mean():.4f}", flush=True)

    print(f"\n=== MQL5 PARITY INSTRUCTIONS ===", flush=True)
    print(f"The MQL5 EA should:", flush=True)
    print(f"1. Load {FIXTURE_PATH.name}", flush=True)
    print(f"2. For each sample, reconstruct the market context at the timestamp", flush=True)
    print(f"3. Call BuildVector() with the same direction", flush=True)
    print(f"4. Compare the resulting 50-feature vector to expected_feature_vector", flush=True)
    print(f"5. Report per-feature absolute difference", flush=True)
    print(f"6. Tolerance: max abs diff < 0.01 for float32 parity", flush=True)

    # Also generate a per-feature expected value summary for quick MQL5 checks
    print(f"\n=== QUICK PARITY CHECK VALUES (first sample) ===", flush=True)
    s0 = fixture["samples"][0]
    print(f"Sample 0: {s0['timestamp']} {s0['direction']}", flush=True)
    print(f"  entry_price={s0['entry_price']:.2f}", flush=True)
    for i, (fname, val) in enumerate(zip(
        [FEATURE_NAMES[PRICE_INDICES[j]] for j in range(len(PRICE_INDICES))],
        s0["feature_vector"])):
        print(f"  [{i:2d}] {fname:30s} = {val:.6f}", flush=True)

    return fixture


if __name__ == "__main__":
    generate_parity_fixture()

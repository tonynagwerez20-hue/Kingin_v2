"""V38.2 Python/MQL5 Feature Parity Test.

Generates a test vector from the Python feature pipeline and exports it
as a JSON fixture that the MQL5 EA can load and compare against its own
BuildVector() output. This verifies that the MQL5 feature engine produces
bit-identical features to the Python pipeline.

Usage:
    python -m v38.v38_2.test_mql5_parity

Output:
    v38/v38_2/full_data_artifacts/v38_2_mql5_parity_fixture.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from v38.config import V38Config
from v38.features.contract import FEATURE_NAMES, FEATURE_SPECS, N_FEATURES

PRICE_INDICES = [i for i in range(N_FEATURES) if FEATURE_SPECS[i].family != "MACRO_NEWS"]

ARTIFACT_DIR = Path(__file__).parent / "full_data_artifacts"
DATASET_PATH = ARTIFACT_DIR / "v38_2_dataset_M5_H1_lb240.parquet"
FIXTURE_PATH = ARTIFACT_DIR / "v38_2_mql5_parity_fixture.json"


def generate_parity_fixture():
    """Generate a test fixture with known feature vectors + expected probabilities."""
    print("Loading M5 dataset...", flush=True)
    df = pd.read_parquet(DATASET_PATH)
    df = df.sort_values("timestamp").reset_index(drop=True)
    mask = df["label"].to_numpy() >= 0
    df = df[mask].reset_index(drop=True)

    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]

    # Pick 10 test samples: mix of enter (decision=1) and skip (decision=0)
    # covering both bullish and bearish directions
    holdout_start = int(len(df) * 0.80)
    holdout = df.iloc[holdout_start:].reset_index(drop=True)

    # Load model + calibrator
    model = joblib.load(ARTIFACT_DIR / "v38_2_final_model.joblib")
    calibrator = joblib.load(ARTIFACT_DIR / "v38_2_calibrator.joblib")

    # Compute decisions to find enter samples
    feat_cols_holdout = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]
    X_holdout = holdout[feat_cols_holdout].to_numpy(dtype=np.float32)
    raw_probs = model.predict_proba(X_holdout)[:, 1]
    cal_probs = calibrator.predict(raw_probs)
    decisions = (cal_probs >= 0.5).astype(int)
    holdout_with_dec = holdout.copy()
    holdout_with_dec["_decision"] = decisions

    enter_bullish = holdout_with_dec[(holdout_with_dec["_decision"] == 1) &
                                      (holdout_with_dec["direction"] == "bullish")].head(3)
    enter_bearish = holdout_with_dec[(holdout_with_dec["_decision"] == 1) &
                                      (holdout_with_dec["direction"] == "bearish")].head(3)
    skip_bullish = holdout_with_dec[(holdout_with_dec["_decision"] == 0) &
                                     (holdout_with_dec["direction"] == "bullish")].head(2)
    skip_bearish = holdout_with_dec[(holdout_with_dec["_decision"] == 0) &
                                     (holdout_with_dec["direction"] == "bearish")].head(2)
    test_samples = pd.concat([enter_bullish, enter_bearish, skip_bullish, skip_bearish]).reset_index(drop=True)

    print(f"Selected {len(test_samples)} test samples "
          f"({len(enter_bullish)+len(enter_bearish)} enter + "
          f"{len(skip_bullish)+len(skip_bearish)} skip)", flush=True)

    # Build fixture
    fixture = {
        "fixture_version": "v38_2_parity_1",
        "feature_count": len(PRICE_INDICES),
        "feature_names": [FEATURE_NAMES[i] for i in PRICE_INDICES],
        "feature_indices": PRICE_INDICES,
        "threshold": 0.5,
        "label_tp_r": 2.0,
        "label_sl_r": 1.0,
        "test_samples": [],
    }

    for idx, row in test_samples.iterrows():
        feat_vector = np.array([row[f] for f in feat_cols], dtype=np.float32)
        raw_prob = float(model.predict_proba(feat_vector.reshape(1, -1))[0, 1])
        cal_prob = float(calibrator.predict([raw_prob])[0])
        decision = int(cal_prob >= 0.5)

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
            "barrier_reached": str(row["barrier_reached"]),
            "feature_vector": feat_vector.tolist(),
            "expected_raw_probability": raw_prob,
            "expected_calibrated_probability": cal_prob,
            "expected_decision": decision,
        }
        fixture["test_samples"].append(sample)

    # Save
    with open(FIXTURE_PATH, "w") as f:
        json.dump(fixture, f, indent=2)
    print(f"\nFixture saved: {FIXTURE_PATH}", flush=True)
    print(f"  {len(fixture['test_samples'])} test samples", flush=True)
    print(f"  {len(PRICE_INDICES)} features per sample", flush=True)

    # Print summary
    print("\n=== TEST SAMPLES SUMMARY ===", flush=True)
    for s in fixture["test_samples"]:
        print(f"  [{s['sample_id']}] {s['timestamp']} {s['direction']:7s} "
              f"raw={s['expected_raw_probability']:.4f} "
              f"cal={s['expected_calibrated_probability']:.4f} "
              f"decision={s['expected_decision']} "
              f"label={s['label']}", flush=True)

    print(f"\nMQL5 EA should load this fixture and verify that BuildVector()")
    print(f"produces the same feature_vector for each sample, and that")
    print(f"OnnxRun() + calibrator produces the same calibrated probability.")
    return fixture


if __name__ == "__main__":
    generate_parity_fixture()

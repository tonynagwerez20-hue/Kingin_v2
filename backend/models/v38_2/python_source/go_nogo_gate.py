"""V38.2 GO/NO-GO model promotion gate.

This gate is implemented now but MUST NOT pass until actual data AND model
validation satisfy every condition. It refuses to permit ONNX export / MQL5
deployment when the readiness gate is BLOCKED or robustness is poor.

Conditions (eventual):
  DATA:    genuine M5/M15, adequate history, acceptable quality, no critical
           missing fields — checked via readiness_gate.evaluate().
  DATASET: genuine candidate states, sufficient sample size, sufficient bearish
           examples, sufficient regime/session diversity, acceptable censoring.
  LEAKAGE: zero violations.
  FEATURES: no unexplained redundant features, no future dependence, stable
            behavior, negative permutation importance investigated, ablation.
  MODEL:   actual LightGBM, predict_proba, walk-forward, untouched final test,
           no threshold optimization vs OOF, calibration on separate temporal data.
  ROBUSTNESS: threshold behavior sensible, survives folds, bull+bear examined,
            regime examined, permutation supports generalization, shuffled baseline
            not similar.

ONLY if all pass do ONNX conversion and MQL5 validation become eligible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from . import V38_2_DIR
from .data.readiness_gate import evaluate as evaluate_readiness


@dataclass
class GoNoGoResult:
    decision: str            # GO | NO_GO
    data_status: str
    blocking_reasons: list = field(default_factory=list)
    data_check_summary: dict = field(default_factory=dict)
    # model-side conditions: unknown until a V38.2 model exists
    model_conditions: dict = field(default_factory=lambda: {
        "dataset_generated": False,
        "leakage_zero_violations": False,
        "feature_audit_passed": False,
        "model_trained_walk_forward": False,
        "calibration_out_of_sample": False,
        "robustness_audit_passed": False,
    })

    @property
    def note(self) -> str:
        return ("V38.2 training was NOT executed because required genuine datasets "
                "are not yet available/validated.") if self.decision == "NO_GO" else ""

    def to_dict(self) -> dict:
        return {"decision": self.decision, "data_status": self.data_status,
                "blocking_reasons": self.blocking_reasons,
                "data_check_summary": self.data_check_summary,
                "model_conditions": self.model_conditions,
                "note": ("V38.2 training was NOT executed because required genuine datasets "
                         "are not yet available/validated.") if self.decision == "NO_GO" else ""}


def evaluate() -> GoNoGoResult:
    rg = evaluate_readiness()
    res = GoNoGoResult(decision="GO", data_status=rg.status,
                       blocking_reasons=list(rg.blocking_reasons),
                       data_check_summary=rg.checks)
    # Data must be READY before any model-side condition is even checkable.
    if rg.status == "BLOCKED":
        res.decision = "NO_GO"
        return res
    # If data were ready, model-side conditions would still need to pass.
    # None of them can be true yet because no V38.2 model has been trained.
    if not all(res.model_conditions.values()):
        res.decision = "NO_GO"
        missing = [k for k, v in res.model_conditions.items() if not v]
        res.blocking_reasons.extend(f"model condition not met: {k}" for k in missing)
    return res


def write_certificate(out_path: Path | None = None) -> GoNoGoResult:
    res = evaluate()
    out = Path(out_path) if out_path else (V38_2_DIR / "v38_2_go_nogo_certificate.json")
    out.write_text(json.dumps(res.to_dict(), indent=2, default=str))
    return res


if __name__ == "__main__":
    r = write_certificate()
    print(json.dumps(r.to_dict(), indent=2, default=str))

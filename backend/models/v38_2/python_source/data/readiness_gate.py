"""Data availability gate — determines whether V38.2 dataset generation is
permitted. Fails loudly when any critical input is absent or invalid.

Required conditions:
  - M5 present and validated
  - M15 present and validated
  - H1 present and validated
  - H4 present and validated
  - macro calendar present and validated
  - UTC alignment valid
  - no unresolved duplicate conflicts
  - no critical schema errors
  - sufficient overlapping history
  - no leakage violations

If any critical input is absent: STATUS = BLOCKED. Downstream training MUST NOT
execute when the gate is BLOCKED. (Enforced by training refusing to run without
a passing gate certificate — see go_nogo_gate.)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pandas as pd

from .. import V38_2_DIR
from .loader import load_h1, load_h4, load_m5, load_m15
from .calendar_loader import load_calendar
from .alignment import align_ltf_to_htf, check_no_lookahead


@dataclass
class GateResult:
    status: str                       # READY | BLOCKED
    blocking_reasons: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    manifest_ref: str = ""

    def to_dict(self) -> dict:
        return {"status": self.status, "blocking_reasons": self.blocking_reasons,
                "checks": self.checks, "manifest_ref": self.manifest_ref}


def _status_of(load_result) -> str:
    """Mirror the manifest's status elevation: AVAILABLE -> VALIDATED only if
    validation.ok, else INVALID; ABSENT stays ABSENT."""
    s = load_result.status
    if s == "ABSENT":
        return "ABSENT"
    if load_result.df is None:
        return "INVALID"
    v = load_result.validation
    if v is None or not v.get("ok"):
        return "INVALID"
    return "VALIDATED"


def _validated(load_result) -> bool:
    return _status_of(load_result) == "VALIDATED"


def evaluate() -> GateResult:
    res = GateResult(status="READY")
    reasons: List[str] = []
    checks = {}

    m5 = load_m5(); m15 = load_m15(); h1 = load_h1(); h4 = load_h4(); cal = load_calendar()

    # --- per-dataset presence + validation ---
    for name, r in [("M5", m5), ("M15", m15), ("H1", h1), ("H4", h4)]:
        st = _status_of(r)
        ok = st == "VALIDATED"
        checks[f"{name}_status"] = st
        checks[f"{name}_validated"] = ok
        if not ok:
            reasons.append(f"{name} dataset {'absent' if st == 'ABSENT' else 'not validated'}")
    cal_st = cal.status if cal.df is not None else "ABSENT"
    if cal_st == "AVAILABLE" and cal.validation and not cal.validation.get("ok"):
        cal_st = "INVALID"
    cal_ok = cal_st == "VALIDATED"
    checks["calendar_status"] = cal_st
    checks["calendar_validated"] = cal_ok
    if not cal_ok:
        reasons.append("economic calendar absent" if cal_st == "ABSENT" else "economic calendar not validated")

    # --- UTC alignment (only meaningful if data present) ---
    alignment_ok = True
    if _status_of(h1) == "VALIDATED" and _status_of(h4) == "VALIDATED":
        al, rep = align_ltf_to_htf(h1.df, h4.df, "H4", "H1")
        no_lookahead = check_no_lookahead(al, "h4_close_ts", "ts")
        checks["H1_to_H4_no_lookahead"] = no_lookahead
        if not no_lookahead:
            alignment_ok = False
            reasons.append("H1->H4 alignment introduces look-ahead")
    if _status_of(m5) == "VALIDATED" and _status_of(h1) == "VALIDATED":
        al, _ = align_ltf_to_htf(m5.df, h1.df, "H1", "M5")
        no_lookahead = check_no_lookahead(al, "h1_close_ts", "ts")
        checks["M5_to_H1_no_lookahead"] = no_lookahead
        if not no_lookahead:
            alignment_ok = False
            reasons.append("M5->H1 alignment introduces look-ahead")
    if _status_of(m15) == "VALIDATED" and _status_of(h1) == "VALIDATED":
        al, _ = align_ltf_to_htf(m15.df, h1.df, "H1", "M15")
        no_lookahead = check_no_lookahead(al, "h1_close_ts", "ts")
        checks["M15_to_H1_no_lookahead"] = no_lookahead
        if not no_lookahead:
            alignment_ok = False
            reasons.append("M15->H1 alignment introduces look-ahead")
    checks["alignment_no_lookahead"] = alignment_ok

    # --- duplicate conflicts (loader resolves via keep_last_logged and logs
    #     every conflict; conflicts are only 'unresolved' if a merge raised) ---
    dup_ok = True
    for name, r in [("M5", m5), ("M15", m15), ("H1", h1), ("H4", h4)]:
        if r.df is None:
            continue
        # r.errors non-empty with a ConflictError message => unresolved
        unresolved = any("conflict" in str(e).lower() for e in r.errors)
        checks[f"{name}_duplicate_conflicts_unresolved"] = unresolved
        if unresolved:
            dup_ok = False
    checks["no_duplicate_conflicts"] = dup_ok
    if not dup_ok:
        reasons.append("unresolved duplicate conflicts")

    # --- sufficient overlapping history (M5/M15 must overlap H1's 2018+ window) ---
    overlap_ok = True
    if _status_of(m5) == "VALIDATED" and _status_of(h1) == "VALIDATED":
        m5_min, m5_max = m5.df["ts"].min(), m5.df["ts"].max()
        h1_min, h1_max = h1.df["ts"].min(), h1.df["ts"].max()
        ov = (min(m5_max, h1_max) - max(m5_min, h1_min)).days
        checks["M5_H1_overlap_days"] = int(ov)
        if ov < 365:
            overlap_ok = False
            reasons.append(f"M5/H1 overlap only {ov} days (< 365)")
    if _status_of(m15) == "VALIDATED" and _status_of(h1) == "VALIDATED":
        m15_min, m15_max = m15.df["ts"].min(), m15.df["ts"].max()
        h1_min, h1_max = h1.df["ts"].min(), h1.df["ts"].max()
        ov = (min(m15_max, h1_max) - max(m15_min, h1_min)).days
        checks["M15_H1_overlap_days"] = int(ov)
        if ov < 365:
            overlap_ok = False
            reasons.append(f"M15/H1 overlap only {ov} days (< 365)")
    checks["sufficient_overlapping_history"] = overlap_ok
    if not overlap_ok:
        reasons.append("insufficient overlapping history")

    if reasons:
        res.status = "BLOCKED"
        res.blocking_reasons = reasons
    res.checks = checks
    res.manifest_ref = str(V38_2_DIR / "v38_2_data_manifest.json")
    return res


def write_certificate(out_path: Path | None = None) -> GateResult:
    res = evaluate()
    out = Path(out_path) if out_path else (V38_2_DIR / "v38_2_readiness_certificate.json")
    out.write_text(json.dumps(res.to_dict(), indent=2, default=str))
    return res


if __name__ == "__main__":
    r = write_certificate()
    print(json.dumps(r.to_dict(), indent=2, default=str))

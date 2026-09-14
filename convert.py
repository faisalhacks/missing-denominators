#!/usr/bin/env python3
"""Convert published AI-incident disclosure rates to common units.

Loads incident records (incidents/*.json), computes per-run and per-agent rates
where they are DERIVABLE from published figures (emitting the arithmetic used),
and prints two tables:

  Table A - naive comparison (rates as published, incompatible units) vs the
            converted per-run rate. The headline figure.
  Table B - the disclosure checklist: which fields are not_recoverable,
            aggregated across all incidents.

Three states, never crossed: recoverable (published), derivable (computed from
published figures, arithmetic shown), not_recoverable (absent). The tool never
estimates, never interpolates, never fills a gap. not_recoverable is the point,
not an error.

stdlib only. No network. Deterministic output.

Usage:
  python convert.py                      # tables to stdout
  python convert.py --out-dir out        # also write out/table_a.md, out/table_b.md
"""
import argparse
import glob
import json
import os
import sys

NUMERIC_FIELDS = ["agent_count", "runs_per_agent", "total_runs",
                  "violation_count", "incident_count",
                  "per_run_rate", "per_agent_rate"]
STATES = {"recoverable", "derivable", "not_recoverable"}


# ---- load + validate (stdlib only; no jsonschema dependency) ----------------
def validate(rec, path):
    errs = []
    for key in ["incident_id", "org", "published_headline"] + NUMERIC_FIELDS:
        if key not in rec:
            errs.append(f"missing field '{key}'")
    for f in NUMERIC_FIELDS:
        m = rec.get(f)
        if not isinstance(m, dict):
            errs.append(f"'{f}' is not an object"); continue
        if m.get("state") not in STATES:
            errs.append(f"'{f}.state' invalid: {m.get('state')!r}")
        if m.get("state") == "not_recoverable" and m.get("value") is not None:
            errs.append(f"'{f}' is not_recoverable but carries a value "
                        f"({m['value']}) - not_recoverable must be null")
        if m.get("value") is not None and not isinstance(m["value"], (int, float)):
            errs.append(f"'{f}.value' not a number: {m['value']!r}")
    pool = rec.get("poolability")
    if pool is not None:
        codes = {"poolable", "no-denominator", "figure-only", "different-estimand", "not-disclosed"}
        if pool.get("reason_code") not in codes:
            errs.append(f"poolability.reason_code invalid: {pool.get('reason_code')!r}")
        if not isinstance(pool.get("poolable"), bool):
            errs.append("poolability.poolable must be boolean")
    if errs:
        raise SystemExit(f"[schema error] {path}:\n  " + "\n  ".join(errs))
    return rec


def load(incidents_dir):
    recs = []
    for p in sorted(glob.glob(os.path.join(incidents_dir, "*.json"))):
        if os.path.basename(p).startswith("_"):     # templates skipped
            continue
        with open(p, encoding="utf-8") as f:
            recs.append(validate(json.load(f), p))
    recs.sort(key=lambda r: r["incident_id"])        # deterministic
    return recs


# ---- derivation -------------------------------------------------------------
def num(m):
    """Return the numeric value if usable (recoverable or derivable), else None."""
    return m["value"] if (m.get("value") is not None
                          and m.get("state") in ("recoverable", "derivable")) else None


def fmt_rate(x):
    # 3 significant figures so the printed rate matches the paper's 4.26e-05
    return f"{x:.3g}"


def derive(rec):
    """Fill total_runs / per_run_rate / per_agent_rate where computable. Marks
    them derivable and writes the arithmetic. Never touches recoverable values."""
    def set_derived(field, value, arithmetic):
        rec[field] = {"value": value, "state": "derivable",
                      "provenance": f"derived: {arithmetic}",
                      "source_url": None, "location": None}

    ac, rpa = num(rec["agent_count"]), num(rec["runs_per_agent"])
    if num(rec["total_runs"]) is None and ac is not None and rpa is not None:
        set_derived("total_runs", ac * rpa, f"{ac:g} agents x {rpa:g} runs/agent = {ac*rpa:g}")

    tr, vc = num(rec["total_runs"]), num(rec["violation_count"])
    if num(rec["per_run_rate"]) is None and tr not in (None, 0) and vc is not None:
        set_derived("per_run_rate", vc / tr, f"{vc:g} / {tr:g} = {fmt_rate(vc/tr)}")

    ac = num(rec["agent_count"])
    numer = vc if vc is not None else num(rec["incident_count"])
    if num(rec["per_agent_rate"]) is None and ac not in (None, 0) and numer is not None:
        set_derived("per_agent_rate", numer / ac, f"{numer:g} / {ac:g} = {fmt_rate(numer/ac)}")
    return rec


# ---- rendering --------------------------------------------------------------
def cell_rate(m):
    v = num(m)
    if v is None:
        return "NOT_RECOVERABLE"
    tag = "recoverable" if m["state"] == "recoverable" else "derivable"
    return f"{fmt_rate(v)}  ({tag})"


def table_a(recs):
    # Poolability criterion (applied identically to all disclosures): a cell is
    # POOLABLE if a per-run rate on the shared containment-breach estimand can be
    # obtained as machine-readable text. Each non-poolable cell is labelled by the
    # FIRST reason it fails. This taxonomy is not overturnable by recovering a
    # value from secondary sources - a different-estimand rate stays non-poolable.
    verified = [r for r in recs if not r.get("pending")]
    n_pool = sum(1 for r in verified if r.get("poolability", {}).get("poolable"))
    L = ["## Table A - naive (as published) vs poolable per-run rate, with reason code",
         "",
         "Left: each source in its own incompatible unit (not a ranking). Right: the",
         "one common unit, the per-run rate, and - where it is not poolable - the",
         "reason. `poolable` if a per-run rate on the shared containment-breach",
         "estimand is obtainable as machine-readable text; otherwise the first",
         "failing reason. Recovering a value from secondary prose does not make a",
         "different-estimand disclosure poolable.",
         "",
         "| disclosure | org | estimand | as published (native unit) | per-run rate | why not poolable |",
         "|---|---|---|---|---|---|"]
    for r in recs:
        pend = " *(PENDING)*" if r.get("pending") else ""
        head = r["published_headline"].replace("|", "\\|")
        pool = r.get("poolability", {})
        code = pool.get("reason_code", "-")
        why = "-" if pool.get("poolable") else code
        L.append(f"| {r['incident_id']}{pend} | {r['org']} | {r.get('estimand','-')} "
                 f"| {head} | {cell_rate(r['per_run_rate'])} | {why} |")
    L += ["",
          f"**{n_pool} of {len(verified)} verified disclosures yields a poolable "
          f"per-run rate** (Anthropic), and it is a detection-limited lower bound. "
          f"The rest are non-poolable for the reason shown, not merely 'hidden'."]
    return "\n".join(L)


def table_b(recs):
    # Counts are over VERIFIED disclosures only. A pending stub is not_recoverable
    # because it was not verified, not because public sources lack it, so counting
    # it as evidence would misrepresent it. Pending records are listed, not counted.
    verified = [r for r in recs if not r.get("pending")]
    pending = [r for r in recs if r.get("pending")]
    L = ["## Table B - disclosure checklist (what public sources do not support)",
         "",
         "Per numeric field, counts across the VERIFIED disclosures and which of",
         "them are `not_recoverable`. This set is the primary output. Pending",
         "(unverified) records are excluded from the counts and listed below.",
         "",
         "| field | recoverable | derivable | not_recoverable | not_recoverable in |",
         "|---|---|---|---|---|"]
    total_nr = 0
    for f in NUMERIC_FIELDS:
        rec_c = der_c = nr_c = 0
        nr_ids = []
        for r in verified:
            st = r[f]["state"]
            if st == "recoverable":
                rec_c += 1
            elif st == "derivable":
                der_c += 1
            else:
                nr_c += 1; nr_ids.append(r["incident_id"])
        total_nr += nr_c
        L.append(f"| {f} | {rec_c} | {der_c} | {nr_c} | {', '.join(nr_ids) or '-'} |")
    L += ["",
          f"**{total_nr} of {len(NUMERIC_FIELDS) * len(verified)} numeric cells are "
          f"not_recoverable** across {len(verified)} verified disclosures."]
    if pending:
        L.append(f"Pending (unverified, excluded from counts): "
                 f"{', '.join(r['incident_id'] for r in pending)}.")
    return "\n".join(L)


def provenance_appendix(recs):
    L = ["## Provenance appendix (derivable arithmetic + not_recoverable reasons)", ""]
    for r in recs:
        L.append(f"### {r['incident_id']} ({r['org']})")
        for f in NUMERIC_FIELDS:
            m = r[f]
            L.append(f"- **{f}** [{m['state']}]: {m['provenance']}"
                     + (f"  <{m['source_url']}>" if m.get("source_url") else ""))
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--incidents-dir",
                    default=os.path.join(os.path.dirname(__file__), "incidents"))
    ap.add_argument("--out-dir", default=None,
                    help="also write table_a.md / table_b.md / provenance.md here")
    a = ap.parse_args()

    recs = [derive(r) for r in load(a.incidents_dir)]
    if not recs:
        sys.exit("no incident records found")

    ta, tb, pa = table_a(recs), table_b(recs), provenance_appendix(recs)
    print(ta + "\n\n" + tb + "\n\n" + pa)

    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        for name, txt in [("table_a.md", ta), ("table_b.md", tb), ("provenance.md", pa)]:
            with open(os.path.join(a.out_dir, name), "w", encoding="utf-8") as f:
                f.write(txt + "\n")
        print(f"\n[wrote {a.out_dir}/table_a.md, table_b.md, provenance.md]", file=sys.stderr)


if __name__ == "__main__":
    main()

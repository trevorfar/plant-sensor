#!/usr/bin/env python3
"""Compare run_sim.py JSON results against specs/specs.yaml. Exit 1 if any metric fails or is missing."""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def evaluate(result: dict, spec: dict) -> list[dict]:
    """Return one row per metric: block, metric, value, min, max, ok, corner, seed."""
    rows = []
    for name, lim in spec["metrics"].items():
        val = result["metrics"].get(name)
        lo, hi = lim.get("min"), lim.get("max")
        ok = val is not None and (lo is None or val >= lo) and (hi is None or val <= hi)
        rows.append({"block": result["block"], "metric": name, "value": val, "min": lo, "max": hi,
                     "ok": ok, "corner": result["corner"], "seed": result.get("seed")})
    return rows


def corner_str(c: dict) -> str:
    return f"T={c['temperature_c']:g}C VSUP=+-{c['supply_v']:g}V process={c['process']}"


def load_results(paths: list[Path]) -> list[dict]:
    files: list[Path] = []
    for p in paths:
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    out = []
    for f in files:
        d = json.loads(f.read_text())
        if "block" in d and "metrics" in d:
            out.append(d)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results", nargs="+", type=Path, help="JSON files or directories")
    ap.add_argument("--specs", type=Path, default=ROOT / "specs/specs.yaml")
    ap.add_argument("--markdown", type=Path, help="append a markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args()
    specs = yaml.safe_load(a.specs.read_text())
    results = load_results(a.results)
    if not results:
        print("no results found", file=sys.stderr)
        return 1
    rows = [r for res in results for r in evaluate(res, specs[res["block"]])]
    fails = [r for r in rows if not r["ok"]]
    md = ["| block | metric | value | min | max | result | corner |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        val = "MISSING" if r["value"] is None else f"{r['value']:.5g}"
        md.append(f"| {r['block']} | {r['metric']} | {val} | {r['min'] if r['min'] is not None else ''} | "
                  f"{r['max'] if r['max'] is not None else ''} | {'PASS' if r['ok'] else '**FAIL**'} | {corner_str(r['corner'])} |")
    print("\n".join(md))
    if a.markdown:
        with open(a.markdown, "a") as fh:
            fh.write("\n".join(md) + "\n\n")
    for r in fails:
        print(f"FAIL {r['block']}.{r['metric']} = {r['value']} (min {r['min']}, max {r['max']}) at {corner_str(r['corner'])}",
              file=sys.stderr)
    print(f"{len(rows) - len(fails)}/{len(rows)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

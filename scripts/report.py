#!/usr/bin/env python3
"""Aggregate corner + Monte Carlo results -> markdown summary, yield table, histograms, MC timing."""
from __future__ import annotations

import argparse, json, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_specs import ROOT, corner_str, evaluate, load_results  # noqa: E402


def fmt_lim(lo: float | None, hi: float | None) -> str:
    return f"{'' if lo is None else lo} .. {'' if hi is None else hi}"


def corner_section(results: list[dict], specs: dict) -> tuple[list[str], int]:
    rows = [r for res in results for r in evaluate(res, specs[res["block"]])]
    by = defaultdict(list)
    for r in rows:
        by[(r["block"], r["metric"])].append(r)
    md = [f"### Corners ({len({corner_str(r['corner']) for r in rows})} corners)", "",
          "| block | metric | limits | worst min | worst max | result |", "|---|---|---|---|---|---|"]
    nfail = 0
    for (b, m), rs in by.items():
        vals = [r["value"] for r in rs if r["value"] is not None]
        bad = [r for r in rs if not r["ok"]]
        nfail += len(bad)
        lo, hi = rs[0]["min"], rs[0]["max"]
        res = "PASS" if not bad else f"**FAIL** ({len(bad)} corners)"
        md.append(f"| {b} | {m} | {fmt_lim(lo, hi)} | {min(vals):.5g} | {max(vals):.5g} | {res} |" if vals
                  else f"| {b} | {m} | {fmt_lim(lo, hi)} | - | - | **FAIL** (no data) |")
    fails = [r for r in rows if not r["ok"]]
    if fails:
        md += ["", "**Failing checks:**", ""]
        md += [f"- `{r['block']}.{r['metric']}` = {r['value']} (limits {fmt_lim(r['min'], r['max'])}) at {corner_str(r['corner'])}"
               for r in fails[:60]]
    return md, nfail


def mc_section(results: list[dict], specs: dict, plotdir: Path) -> list[str]:
    plotdir.mkdir(parents=True, exist_ok=True)
    data = defaultdict(list)
    block_ok = defaultdict(list)
    for res in results:
        rows = evaluate(res, specs[res["block"]])
        block_ok[res["block"]].append(all(r["ok"] for r in rows))
        for r in rows:
            data[(r["block"], r["metric"])].append((r["value"], r["ok"]))
    md = [f"### Monte Carlo ({max((len(v) for v in block_ok.values()), default=0)} runs per block)", "",
          "| block | metric | limits | mean | sigma | min | max | yield |", "|---|---|---|---|---|---|---|---|"]
    for (b, m), vs in sorted(data.items()):
        lim = specs[b]["metrics"][m]
        arr = np.array([v for v, _ in vs if v is not None], float)
        yld = 100.0 * sum(ok for _, ok in vs) / len(vs)
        if arr.size:
            md.append(f"| {b} | {m} | {fmt_lim(lim.get('min'), lim.get('max'))} | {arr.mean():.5g} | {arr.std():.3g} | "
                      f"{arr.min():.5g} | {arr.max():.5g} | {'**' if yld < 100 else ''}{yld:.1f} %{'**' if yld < 100 else ''} |")
            fig, ax = plt.subplots(figsize=(5, 3))
            ax.hist(arr, bins=40, color="#4a7ab5")
            for key, ls in (("min", "--"), ("max", "--")):
                if key in lim:
                    ax.axvline(lim[key], color="#c0392b", ls=ls, lw=1)
            ax.set_title(f"{b}.{m}  yield {yld:.1f} %", fontsize=9)
            ax.set_xlabel(m); ax.set_ylabel("runs")
            fig.tight_layout(); fig.savefig(plotdir / f"{b}__{m}.png", dpi=110); plt.close(fig)
    md += ["", "| block | yield (all metrics) |", "|---|---|"]
    md += [f"| {b} | {100 * np.mean(v):.1f} % |" for b, v in sorted(block_ok.items())]
    return md


def timing_section(mcdirs: list[Path]) -> list[str]:
    metas = [json.loads(f.read_text()) for d in mcdirs if d.is_dir() for f in d.rglob("shard_meta_*.json")]
    if not metas:
        return []
    wall = max(m["end"] for m in metas) - min(m["start"] for m in metas)
    serial = sum(m["wall_s"] for m in metas)
    cpu = sum(m["cpu_sim_s"] for m in metas)
    return ["### Monte Carlo timing", "",
            f"- shards: {len(metas)}, simulations: {sum(m['sims'] for m in metas)}",
            f"- wall-clock (first shard start -> last shard end): **{wall:.1f} s**",
            f"- equivalent serial time (sum of shard job times): **{serial:.1f} s** -> speed-up {serial / max(wall, 1e-9):.1f}x",
            f"- summed ngspice time across all workers: {cpu:.1f} s"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corners", nargs="*", type=Path, default=[], help="dirs/files with corner JSON")
    ap.add_argument("--mc", nargs="*", type=Path, default=[], help="dirs/files with Monte Carlo JSON")
    ap.add_argument("--specs", type=Path, default=ROOT / "specs/specs.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "results/report")
    ap.add_argument("--summary", type=Path, help="also append markdown here, e.g. $GITHUB_STEP_SUMMARY")
    a = ap.parse_args()
    specs = yaml.safe_load(a.specs.read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    md = ["## Plant-sensor AFE simulation report", ""]
    nfail = 0
    if a.corners:
        sec, nfail = corner_section(load_results(a.corners), specs)
        md += sec + [""]
    if a.mc:
        mc = [r for r in load_results(a.mc) if r.get("seed") is not None]
        md += mc_section(mc, specs, a.out / "histograms") + [""] + timing_section(a.mc) + [""]
    md.append(f"**Overall corner result: {'PASS' if nfail == 0 else f'FAIL ({nfail} failing checks)'}**")
    text = "\n".join(md) + "\n"
    (a.out / "report.md").write_text(text)
    if a.summary:
        with open(a.summary, "a") as fh:
            fh.write(text)
    print(text)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())

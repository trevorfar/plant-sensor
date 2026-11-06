#!/usr/bin/env python3
"""Run Monte Carlo seeds for shard k of K: every block in specs.yaml, runs/K seeds, in parallel across cores."""
from __future__ import annotations

import argparse, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_sim import ROOT, load_bom, run_block  # noqa: E402


def _job(args: tuple) -> dict:
    block, spec, bom, t, v, seed, ngspice = args
    return run_block(block, spec, bom, t, v, "typ", seed, ngspice)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shard", type=int, required=True, help="shard index k (0-based)")
    ap.add_argument("--shards", type=int, help="K; default from montecarlo.yaml")
    ap.add_argument("--runs", type=int, help="total runs; default from montecarlo.yaml")
    ap.add_argument("--config", type=Path, default=ROOT / "sim/montecarlo.yaml")
    ap.add_argument("--specs", type=Path, default=ROOT / "specs/specs.yaml")
    ap.add_argument("--bom", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, default=ROOT / "results/mc")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--ngspice", default="ngspice")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text())
    if cfg.get("distribution", "gaussian") != "gaussian":
        raise SystemExit("only gaussian distribution is implemented")
    runs, shards = a.runs or cfg["runs"], a.shards or cfg["shards"]
    per = -(-runs // shards)
    first, last = a.shard * per, min(runs, (a.shard + 1) * per)
    specs = yaml.safe_load(a.specs.read_text())
    bom = load_bom(a.bom)
    t, v = cfg.get("temperature_c", 25), cfg.get("supply_v", 5.0)
    jobs = [(b, specs[b], bom, t, v, cfg["seed"] + i, a.ngspice) for i in range(first, last) for b in specs]
    a.outdir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with ProcessPoolExecutor(max_workers=a.jobs) as pool:
        results = list(pool.map(_job, jobs, chunksize=4))
    end = time.time()
    for r in results:
        (a.outdir / f"{r['block']}__seed{r['seed']}.json").write_text(json.dumps(r))
    meta = {"shard": a.shard, "shards": shards, "seeds": [cfg["seed"] + first, cfg["seed"] + last - 1],
            "sims": len(jobs), "start": start, "end": end, "wall_s": round(end - start, 2),
            "cpu_sim_s": round(sum(r["elapsed_s"] for r in results), 2), "workers": a.jobs}
    (a.outdir / f"shard_meta_{a.shard:02d}.json").write_text(json.dumps(meta, indent=1))
    bad = sum(1 for r in results if any(v is None for v in r["metrics"].values()))
    print(f"shard {a.shard}/{shards}: {len(jobs)} sims in {meta['wall_s']} s on {a.jobs} workers, {bad} with missing metrics")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run one (or every) testbench at one corner or Monte Carlo seed and write JSON metrics.

Component values, Tolerance and TempCo come from the KiCad BOM CSV (kicad-cli sch export bom).
Every `.param <REFDES> = <value>` line in a testbench whose name is a BOM reference is overwritten.
"""
from __future__ import annotations

import argparse, csv, json, math, re, subprocess, sys, tempfile, time, zlib
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
SUFFIX = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "µ": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
PARAM_RE = re.compile(r"^\.param\s+(\w+)\s*=\s*(\S+)\s*$", re.I)


def spice_value(text: str) -> float | None:
    """Parse '10k', '4.7u', '100Meg', '1G', '8.35k' -> float. Returns None if not a SPICE number."""
    m = re.fullmatch(r"\s*([-+]?\d*\.?\d+(?:e[-+]?\d+)?)(meg|[tgkmuµnpf])?[a-z]*\s*", text, re.I)
    if not m:
        return None
    return float(m.group(1)) * SUFFIX.get((m.group(2) or "").lower(), 1.0)


def pct(text: str) -> float:
    m = re.match(r"\s*([\d.]+)\s*%", text or "")
    return float(m.group(1)) / 100 if m else 0.0


def ppm(text: str) -> float:
    m = re.match(r"\s*([-+]?[\d.]+)\s*ppm", text or "", re.I)
    return float(m.group(1)) * 1e-6 if m else 0.0


def expand_refs(cell: str) -> list[str]:
    refs: list[str] = []
    for tok in re.split(r"[,\s]+", cell.strip()):
        m = re.fullmatch(r"([A-Za-z#]+)(\d+)-\1?(\d+)", tok)
        if m:
            refs += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)]
        elif tok:
            refs.append(tok)
    return refs


def load_bom(path: Path) -> dict[str, dict]:
    bom: dict[str, dict] = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            refcol = row.get("Reference") or row.get("Refs") or ""
            for ref in expand_refs(refcol):
                bom[ref] = {"value": row.get("Value", ""), "tol": pct(row.get("Tolerance", "")),
                            "tc": ppm(row.get("TempCo", ""))}
    return bom


def resolve_values(tb_text: str, bom: dict, temp_c: float, process: str, seed: int | None) -> tuple[dict, list[str]]:
    names = [m.group(1) for line in tb_text.splitlines() if (m := PARAM_RE.match(line.strip()))]
    refs = sorted(n for n in names if re.fullmatch(r"[RCL]\d+", n, re.I))
    rng = np.random.default_rng(seed) if seed is not None else None
    out, warnings = {}, []
    for ref in refs:
        if ref not in bom:
            raise SystemExit(f"testbench parameter {ref} has no BOM entry - schematic and testbench out of sync")
        nominal = spice_value(bom[ref]["value"])
        if nominal is None:
            raise SystemExit(f"{ref}: BOM value '{bom[ref]['value']}' is not SPICE-parsable")
        tol = bom[ref]["tol"]
        if rng is not None:
            factor = 1.0 + rng.normal(0.0, tol / 3.0)
        else:
            factor = {"min": 1.0 - tol, "typ": 1.0, "max": 1.0 + tol}[process]
        out[ref] = nominal * factor * (1.0 + bom[ref]["tc"] * (temp_c - 25.0))
    for line in tb_text.splitlines():
        m = PARAM_RE.match(line.strip())
        if m and m.group(1) in out:
            tb_nom = spice_value(m.group(2))
            bom_nom = spice_value(bom[m.group(1)]["value"])
            if tb_nom and bom_nom and not math.isclose(tb_nom, bom_nom, rel_tol=1e-9):
                warnings.append(f"{m.group(1)}: testbench default {m.group(2)} != BOM {bom[m.group(1)]['value']} (BOM used)")
    return out, warnings


def run_block(block: str, spec: dict, bom: dict, temp_c: float, supply: float, process: str,
              seed: int | None, ngspice: str = "ngspice") -> dict:
    tb = ROOT / spec["testbench"]
    text = tb.read_text()
    values, warns = resolve_values(text, bom, temp_c, process, seed)
    values["VSUP"] = supply
    lines = []
    for line in text.splitlines():
        m = PARAM_RE.match(line.strip())
        if m and m.group(1) in values:
            line = f".param {m.group(1)} = {values[m.group(1)]:.9g}"
        elif line.strip().lower().startswith(".include"):
            inc = line.split(None, 1)[1].strip().strip('"')
            line = f'.include "{(tb.parent / inc).resolve()}"'
        elif line.strip().lower() == ".control":
            lines.append(f".options temp={temp_c}")
        lines.append(line)
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        cir = Path(td) / tb.name
        cir.write_text("\n".join(lines) + "\n")
        proc = subprocess.run([ngspice, "-b", str(cir)], capture_output=True, text=True, timeout=300, cwd=td)
    metrics: dict[str, float | None] = {name: None for name in spec["metrics"]}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "METRIC":
            metrics[parts[1]] = float(parts[2]) if len(parts) > 2 else None
    errors = [l for l in (proc.stdout + proc.stderr).splitlines() if l.lower().startswith("error")]
    return {"block": block, "testbench": spec["testbench"],
            "corner": {"temperature_c": temp_c, "supply_v": supply, "process": process if seed is None else "mc"},
            "seed": seed, "metrics": metrics, "elapsed_s": round(time.time() - t0, 3),
            "warnings": warns, "ngspice_errors": errors[:10]}


def corner_from_index(path: Path, idx: int) -> tuple[float, float, str]:
    c = yaml.safe_load(path.read_text())
    combos = [(t, v, p) for t in c["temperature_c"] for v in c["supply_v"] for p in c["process"]]
    return combos[idx]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block", default="all", help="spec key in specs.yaml, or 'all'")
    ap.add_argument("--specs", type=Path, default=ROOT / "specs/specs.yaml")
    ap.add_argument("--bom", type=Path, required=True, help="BOM CSV with Reference,Value,Tolerance,TempCo")
    ap.add_argument("--corner-index", type=int, help="index 0..N-1 into corners.yaml (overrides T/V/process)")
    ap.add_argument("--corners", type=Path, default=ROOT / "sim/corners.yaml")
    ap.add_argument("--temperature", type=float, default=25.0)
    ap.add_argument("--supply", type=float, default=5.0, help="magnitude of the +-5VA rails")
    ap.add_argument("--process", choices=["min", "typ", "max"], default="typ")
    ap.add_argument("--seed", type=int, help="Monte Carlo seed (gaussian, tolerance = 3 sigma)")
    ap.add_argument("--outdir", type=Path, default=ROOT / "results")
    ap.add_argument("--ngspice", default="ngspice")
    a = ap.parse_args()
    specs = yaml.safe_load(a.specs.read_text())
    blocks = list(specs) if a.block == "all" else [a.block]
    t, v, p = (corner_from_index(a.corners, a.corner_index) if a.corner_index is not None
               else (a.temperature, a.supply, a.process))
    bom = load_bom(a.bom)
    a.outdir.mkdir(parents=True, exist_ok=True)
    for b in blocks:
        res = run_block(b, specs[b], bom, t, v, p, a.seed, a.ngspice)
        tag = f"seed{a.seed}" if a.seed is not None else f"T{t:g}_V{v:g}_{p}"
        out = a.outdir / f"{b}__{tag}.json"
        out.write_text(json.dumps(res, indent=1))
        for w in res["warnings"] + res["ngspice_errors"]:
            print(f"[{b}] {w}", file=sys.stderr)
        print(f"{b:16s} {tag:20s} " + " ".join(f"{k}={val:.6g}" if val is not None else f"{k}=NONE"
                                               for k, val in res["metrics"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

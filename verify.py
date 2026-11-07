#!/usr/bin/env python3
"""Side-by-side timing comparison of two GitHub Actions workflows (default: GitHub baseline vs Namespace).

    python3 verify.py                    # latest commit that has a run of BOTH workflows
    python3 verify.py --sha d3e8943      # a specific commit
    python3 verify.py --runs 111 222     # two specific run ids
    python3 verify.py --steps            # also show every step

Uses only the standard library. Set GITHUB_TOKEN (or GH_TOKEN) for private repos / higher rate limits.
Matrix copies such as "corners (5)" are grouped: the table shows how many ran, their wall-clock span
(first start -> last finish) and their summed runner time.
"""
from __future__ import annotations

import argparse, json, os, re, subprocess, sys, urllib.request
from collections import defaultdict
from datetime import datetime

API = "https://api.github.com"


def get(path: str) -> dict:
    req = urllib.request.Request(API + path, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def secs(a: str | None, b: str | None) -> float | None:
    a, b = ts(a), ts(b)
    return (b - a).total_seconds() if a and b else None


def repo_from_git() -> str:
    url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if not m:
        sys.exit("can't read the repo from `git remote get-url origin`; pass --repo owner/name")
    return m.group(1)


def runs_for(repo: str, wf: str) -> list[dict]:
    try:
        return get(f"/repos/{repo}/actions/workflows/{wf}/runs?per_page=30")["workflow_runs"]
    except urllib.error.HTTPError as e:
        print(f"warning: no runs for {wf} ({e.code}); is it pushed?", file=sys.stderr)
        return []


def jobs_for(repo: str, run_id: int) -> list[dict]:
    jobs, page = [], 1
    while True:
        batch = get(f"/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100&page={page}")["jobs"]
        jobs += batch
        if len(batch) < 100:
            return jobs
        page += 1


def summarize(repo: str, run: dict) -> dict:
    """Return {row label: seconds or text} for one run."""
    jobs = jobs_for(repo, run["id"])
    out: dict[str, object] = {"run id": run["id"], "commit": run["head_sha"][:7],
                              "status": run["conclusion"] or run["status"]}
    starts = [j["started_at"] for j in jobs if j["started_at"]]
    ends = [j["completed_at"] for j in jobs if j["completed_at"]]
    if starts and ends:
        out["TOTAL wall-clock (first job start -> last job end)"] = secs(min(starts), max(ends))
    out["TOTAL queue before first job"] = secs(run["run_started_at"], min(starts)) if starts else None
    out["TOTAL runner time (sum of all jobs)"] = sum(secs(j["started_at"], j["completed_at"]) or 0 for j in jobs)
    out["TOTAL jobs"] = len(jobs)

    groups: dict[str, list[dict]] = defaultdict(list)
    for j in jobs:
        groups[re.sub(r" \(.*\)$", "", j["name"])].append(j)
    for g, js in groups.items():
        s = [j["started_at"] for j in js if j["started_at"]]
        e = [j["completed_at"] for j in js if j["completed_at"]]
        label = f"{g} x{len(js)}" if len(js) > 1 else g
        out[f"job  {label}: wall"] = secs(min(s), max(e)) if s and e else None
        if len(js) > 1:
            out[f"job  {label}: runner time"] = sum(secs(j["started_at"], j["completed_at"]) or 0 for j in js)
        # step durations, averaged over matrix copies
        steps: dict[str, list[float]] = defaultdict(list)
        for j in js:
            for st in j.get("steps", []):
                d = secs(st["started_at"], st["completed_at"])
                if d is not None:
                    steps[st["name"]].append(d)
        for name, ds in steps.items():
            key = f"step {g} / {name}" + (" (avg)" if len(js) > 1 else "")
            out[key] = sum(ds) / len(ds)
    return out


def fmt(v: object) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.0f} s" if v < 120 else f"{v:.0f} s ({v / 60:.1f} min)"
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="owner/name (default: from git remote)")
    ap.add_argument("--workflows", nargs=2, default=["ci-baseline.yml", "ci-namespace.yml"],
                    metavar=("LEFT", "RIGHT"), help="workflow file names")
    ap.add_argument("--labels", nargs=2, default=["GitHub", "Namespace"], metavar=("LEFT", "RIGHT"))
    ap.add_argument("--sha", help="compare the runs of this commit (prefix ok)")
    ap.add_argument("--runs", nargs=2, type=int, metavar=("LEFT_ID", "RIGHT_ID"), help="explicit run ids")
    ap.add_argument("--steps", action="store_true", help="show per-step rows too")
    a = ap.parse_args()
    repo = a.repo or repo_from_git()

    if a.runs:
        picked = [get(f"/repos/{repo}/actions/runs/{i}") for i in a.runs]
    else:
        lists = [runs_for(repo, wf) for wf in a.workflows]
        if a.sha:
            picked = [next((r for r in l if r["head_sha"].startswith(a.sha)), None) for l in lists]
        else:
            right_shas = {r["head_sha"] for r in lists[1]}
            common = next((r["head_sha"] for r in lists[0] if r["head_sha"] in right_shas), None)
            if common:
                picked = [next(r for r in l if r["head_sha"] == common) for l in lists]
            else:
                print("note: no commit has runs of both workflows; using each one's latest run", file=sys.stderr)
                picked = [l[0] if l else None for l in lists]

    cols = [summarize(repo, r) if r else {} for r in picked]
    rows = list(dict.fromkeys(k for c in cols for k in c))   # keep order, union of both sides
    if not a.steps:
        rows = [r for r in rows if not r.startswith("step ")]

    w0 = max(len(r) for r in rows)
    w = max(14, *(len(fmt(c.get(r))) for c in cols for r in rows))
    print(f"{'':{w0}} | {a.labels[0]:>{w}} | {a.labels[1]:>{w}} | {'right vs left':>14}")
    print("-" * (w0 + 2 * w + 25))
    for r in rows:
        left, right = cols[0].get(r), cols[1].get(r)
        delta = ""
        if isinstance(left, float) and isinstance(right, float) and left > 0 and right > 0:
            ratio = max(left, right) / min(left, right)
            delta = "same" if ratio < 1.05 else (f"{ratio:.2f}x faster" if right < left else f"{ratio:.2f}x slower")
        print(f"{r:{w0}} | {fmt(left):>{w}} | {fmt(right):>{w}} | {delta:>14}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
